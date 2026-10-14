"""Fake-client only. No subprocess, phone connection, NN, actual plan use."""
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import d1_a24_laptop_control as control
from d1_a24_laptop_mock import fixture_manifest, replay_mock
from d1_a24_laptop_validator import NS, ValidationError, sha256


class FakeAdb:
    actual_calls = 0

    def __init__(self, manifest, *, ap=30.0, fingerprint="SOFTWARE-MOCK-FINGERPRINT", corrupt=False, active_pid=False, pid_outputs=None, pid_error_process=None,
                 cleanup_delay_ns=0, cleanup_failed=False, summary_status="COMPLETED_PENDING_HOST_VALIDATION", failure_evidence=False, archive_cleanup_failed=False, closure_delay_ns=None):
        self.manifest = manifest
        self.clock = NS
        self.origin = None
        self.calls = []
        self.ap = ap
        self.fingerprint = fingerprint
        self.corrupt = corrupt
        self.active_pid = active_pid
        self.pid_outputs = pid_outputs or {}
        self.pid_error_process = pid_error_process
        self.cleanup_delay_ns = cleanup_delay_ns
        self.cleanup_failed = cleanup_failed
        self.failure_evidence = failure_evidence
        self.archive_cleanup_failed = archive_cleanup_failed
        self.summary = {"software_mock": True, "device_verified": False, "status": summary_status}
        self.cleanup = {"status": "DRAIN_FAILED" if cleanup_failed else "DRAINED", "actual_return_confirmed": not cleanup_failed,
                        "error": "SOFTWARE_MOCK_DRAIN_FAILURE" if cleanup_failed else None, "session_failure": None}
        self.cleanup_observed_at = None
        self.closure_delay_ns=closure_delay_ns
        self.closed={'status':'SYNCED_AND_CLOSED','session_id':manifest['session_id'],'process_id':123}
        self.tar_observed_at=None

    def sleep_ns(self, nanoseconds):
        self.clock += nanoseconds

    def command(self, *args, **kwargs):
        self.calls.append(args)
        self.clock += 1_000
        if args == ("shell", "getprop", "ro.build.fingerprint"):
            return self.fingerprint.encode()
        if args == ("shell", "getprop", "ro.product.model"):
            return b"SM-A245N"
        if args[:2] == ("shell", "pidof"):
            if args[2] == self.pid_error_process:
                raise ValidationError("SOFTWARE_MOCK_PID_LOOKUP_COMMAND_ERROR")
            if args[2] in self.pid_outputs:
                return self.pid_outputs[args[2]]
            return b"12345\n" if self.active_pid and args[2] == control.PACKAGE else b""
        if args == ("shell", "cat", "/proc/uptime"):
            return (str(self.clock / NS) + " 0\n").encode()
        if args == ("shell", "dumpsys", "thermalservice"):
            return f"Current temperatures from HAL:\nTemperature{{mValue={self.ap}, mType=0, mName=MOCK_AP, mStatus=0}}\n".encode()
        if args == ("shell", "dumpsys", "battery"):
            return b"AC powered: false\nUSB powered: false\nWireless powered: false\nlevel: 60\nscale: 100\n"
        if args[-1].endswith("ready.json"):
            return json.dumps({"session_id": self.manifest["session_id"], "plan_sha256": self.manifest["plan_sha256"], "ready_ns": NS}).encode()
        if args[0] == "shell" and args[-1].endswith("start_approval.json"):
            self.origin = self.clock
        if args[-1].endswith("summary.json"):
            if self.origin is None or self.clock - self.origin < 210 * NS:
                raise ValidationError("fake file not yet produced")
            return json.dumps(self.summary).encode()
        if args[-1].endswith("cleanup.json"):
            if self.origin is None or self.clock - self.origin < 210 * NS + self.cleanup_delay_ns:
                raise ValidationError("fake cleanup not yet atomically published")
            self.cleanup_observed_at = self.clock
            return json.dumps(self.cleanup).encode()
        if args[-1].endswith("failure.json"):
            if not self.failure_evidence or self.origin is None:
                raise ValidationError("fake failure artifact absent")
            return b'{"status":"FAILED","reason":"SOFTWARE_MOCK_REQUEST_ERROR"}'
        if args[-1].endswith('journal_closed.json'):
            if self.origin is None or self.closure_delay_ns is None or self.clock-self.origin<210*NS+self.closure_delay_ns:
                return ('cat: '+args[-1]+': No such file or directory\n').encode()
            return json.dumps(self.closed).encode()
        if "tar" in args:
            self.tar_observed_at=self.clock
            events, rows = replay_mock(self.manifest, t0_ns=self.origin)
            if self.corrupt:
                events = [row for row in events if row["kind"] != "dispatch_stop"]
            cleanup = {**self.cleanup, "status": "DRAIN_FAILED"} if self.archive_cleanup_failed else self.cleanup
            data = {"events.jsonl": "".join(json.dumps(row) + "\n" for row in events).encode(), "requests.json": json.dumps(rows).encode(),
                    "summary.json": json.dumps(self.summary).encode(), "cleanup.json": json.dumps(cleanup).encode()}
            if self.closure_delay_ns is not None and self.clock-self.origin>=210*NS+self.closure_delay_ns:
                data['journal_closed.json']=json.dumps(self.closed).encode()
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w") as archive:
                for name, contents in data.items():
                    member = tarfile.TarInfo(f"files/a24_laptop_results/{self.manifest['session_id']}/{name}")
                    member.size = len(contents)
                    archive.addfile(member, io.BytesIO(contents))
            return stream.getvalue()
        return b""


class FutureControllerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.manifest = fixture_manifest("IDLE_RESIDENT")
        self.manifest.update({"plan_id": "SOFTWARE-MOCK-ONLY-UNRELATED-TO-PROPOSED-DEVICE-PLAN", "plan_sha256": "1" * 64,
                              "models": {key: {"software_mock": True} for key in ("C_CPU", "C_GPU", "D_CPU", "D_GPU")}})
        self.manifest.update({"execution_authorized": True, "device_status": "DEVICE_APPROVED_FOR_NEW_CONTRACT", "mock": False})
        bundle = self.root / "bundle"
        bundle.mkdir()
        manifest_file = bundle / "session_manifest.json"
        manifest_file.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.gate = {"schema": "a24-laptop-frozen-gate-v1", "frozen": True, "sensor_name": "MOCK_AP", "sensor_type": 0,
            "Tref_c": 30.0, "tref_tolerance_c": 0.5, "maximum_abs_slope_c_per_min": 0.1,
            "history_ns": 60 * NS, "maximum_gate_wait_ns": 600 * NS,
            "minimum_SOC_percent": 40, "maximum_SOC_percent": 80, "require_unplugged": True,
            "hal_poll_period_ns": 10 * NS, "maximum_observation_gap_ns": 15 * NS,
            "status_poll_period_ns": 10 * NS, "ready_timeout_ns": 60 * NS, "session_timeout_ns": 240 * NS,
            "maximum_raw_bytes": 1_000_000, "environment_reviewed": True, "screen_contract": "SOFTWARE_MOCK_ONLY"}
        gate_bytes = json.dumps(self.gate).encode()
        for name in ("fake.apk", "fake-adb.txt", "source_sha_manifest.json", "stdlib.lock"):
            (self.root / name).write_bytes(b"SOFTWARE_MOCK_BYTES_NEVER_EXECUTED")
        self.source_root = self.root / "source_fixture"
        self.fixture_controller = self.source_root / "tools/d1_a24_laptop_control.py"
        self.fixture_controller.parent.mkdir(parents=True)
        self.fixture_controller.write_bytes(Path(control.__file__).read_bytes())
        self.fixture_source = self.source_root / "tools/mock_source.py"
        self.fixture_source.write_bytes(b"SOFTWARE_MOCK_SOURCE_NOT_EXECUTED")
        self.source_manifest = {"schema": control.SOURCE_MANIFEST_SCHEMA, "files": [
            {"path": path.relative_to(self.source_root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in (self.fixture_controller, self.fixture_source)]}
        (self.root / "source_sha_manifest.json").write_text(json.dumps(self.source_manifest),encoding="utf-8")
        # Only the helper's physical fixture path is injected. The independent
        # actual-controller __file__/SHA authorization check remains unchanged.
        self.controller_source_patch = mock.patch.object(control,"CONTROLLER_SOURCE_FILE",self.fixture_controller)
        self.controller_source_patch.start()
        self.addCleanup(self.controller_source_patch.stop)
        apk_sha = sha256(self.root / "fake.apk")
        for model in self.manifest["models"].values():
            model["identity"] = {"session_id": self.manifest["session_id"]}
            model["target"] = {"adb_serial": "SOFTWARE_MOCK_ONLY", "build_fingerprint": "SOFTWARE-MOCK-FINGERPRINT", "apk_sha256": apk_sha,
                "package_name": control.PACKAGE, "model": "SM-A245N", "api_level": 36, "ram_bytes": 1_000_000,
                **{key: "SOFTWARE_MOCK_REGISTRATION_ONLY" for key in ("device_id", "abi", "cpu_abi", "cpu_features", "soc", "manufacturer", "gpu_vendor", "gpu_renderer", "gpu_driver", "android_release")}}
        manifest_file.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.config = {"manifest_bytes": manifest_file.read_bytes(), "manifest_sha256": sha256(manifest_file),
            "gate_bytes": gate_bytes, "gate_sha256": control.hashlib.sha256(gate_bytes).hexdigest(),
            "bundle_root": str(bundle), "files": [{"path": "session_manifest.json", "bytes": manifest_file.stat().st_size, "sha256": sha256(manifest_file)}],
            "apk": {"path": str(self.root / "fake.apk"), "sha256": apk_sha}, "adb": {"path": str(self.root / "fake-adb.txt"), "sha256": sha256(self.root / "fake-adb.txt")},
            "apk_identity": {"package": control.PACKAGE, "signature_verification": "PASS", "apk_sha256": apk_sha, "signer_certificate_sha256": "2" * 64},
            "source_code_manifest": str(self.root / "source_sha_manifest.json"), "source_code_sha256": sha256(self.root / "source_sha_manifest.json"),
            "source_root": str(self.source_root),
            "host_dependency_lock": str(self.root / "stdlib.lock"), "host_dependency_lock_sha256": sha256(self.root / "stdlib.lock"),
            "registry_root": str(self.root / control.PROTOCOL / self.manifest["plan_id"]), "output_root": str(self.root / "mock_recovery")}
        self.auth = {"schema": "a24-laptop-control-authorization-v1", "authorization": "USER_EXPLICIT_FUTURE_A24_MEASUREMENT", "scope": "one_new_session",
            "session_id": self.manifest["session_id"], "plan_sha256": self.manifest["plan_sha256"], "manifest_sha256": self.config["manifest_sha256"],
            "gate_sha256": self.config["gate_sha256"], "apk_sha256": apk_sha, "serial": "SOFTWARE_MOCK_ONLY", "fingerprint": "SOFTWARE-MOCK-FINGERPRINT", "expected_model": "SM-A245N",
            "source_code_sha256": self.config["source_code_sha256"], "host_dependency_lock_sha256": self.config["host_dependency_lock_sha256"], "control_source_sha256": sha256(Path(control.__file__))}
        self.auth.update({"api_level": 36, "ram_bytes": 1_000_000})

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_scope_never_constructs_device_client_or_registry(self):
        with mock.patch.object(control, "NativeAdbClient", side_effect=AssertionError("native client constructed")):
            with self.assertRaisesRegex(ValidationError, "PREPARATION_ONLY"):
                control.run_one(self.manifest, self.config, self.auth, self.gate)
        self.assertFalse(Path(self.config["registry_root"]).exists())

    def test_current_preparation_authorization_never_grants_a_run(self):
        self.auth["authorization"] = "PREPARATION_ONLY_NO_DEVICE_COMMANDS"
        with self.assertRaisesRegex(ValidationError, "preparation scope"):
            control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=FakeAdb(self.manifest))
        self.assertFalse(Path(self.config["registry_root"]).exists())

    def test_unfrozen_Tref_or_gap_refuses_before_registry(self):
        self.gate["frozen"] = False
        with self.assertRaisesRegex(ValidationError, "not frozen"):
            control.check_authorization(self.manifest, self.config, self.auth, self.gate, execute_authorized=True)

    def test_source_or_input_bytes_changed_fail_closed(self):
        (self.root / "bundle/session_manifest.json").write_bytes(b"changed")
        with self.assertRaisesRegex(ValidationError, "bytes/SHA"):
            control.check_authorization(self.manifest, self.config, self.auth, self.gate, execute_authorized=True)

    def test_legacy_registry_namespace_is_never_reused(self):
        self.config["registry_root"] = str(self.root / "legacy-resident03-registry")
        fake = FakeAdb(self.manifest)
        with self.assertRaisesRegex(ValidationError, "namespace"):
            control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        self.assertFalse(fake.calls)

    def test_fake_full_ready_history_claim_recovery_trace_flow(self):
        fake = FakeAdb(self.manifest)
        with mock.patch("subprocess.run", side_effect=AssertionError("physical command executed")):
            result = control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        self.assertEqual(result["status"], "COMPLETE_TRACE_RECOVERED")
        self.assertEqual(result["actual_adb_calls"], 0)
        state = Path(self.config["registry_root"]) / self.manifest["session_id"]
        start, complete = control.load_json(state / "START.json"), control.load_json(state / "COMPLETE.json")
        self.assertEqual(start["attempt_id"], complete["attempt_id"])
        output = Path(self.config["output_root"]) / self.manifest["session_id"]
        self.assertTrue((output / "host_hal_raw.jsonl").is_file())
        from d1_a24_laptop_recover import verify_local_delivery
        self.assertTrue(verify_local_delivery(output, control.load_json(output / "transport_manifest.json")))
        with self.assertRaisesRegex(ValidationError, "identity reuse"):
            control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)

    def test_fake_AP_reject_preserves_all_attempt_without_START(self):
        fake = FakeAdb(self.manifest, ap=35.0)
        result = control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        self.assertEqual(result["status"], "PRESTART_REJECT")
        state = Path(self.config["registry_root"]) / self.manifest["session_id"]
        self.assertTrue((state / "PRESTART_REJECT.json").is_file())
        self.assertTrue((state / "host_hal_partial.jsonl").is_file())
        self.assertFalse((state / "START.json").exists())

    def test_fake_device_identity_mismatch_logs_rejection_not_start(self):
        fake = FakeAdb(self.manifest, fingerprint="WRONG-MOCK-PHONE")
        with self.assertRaisesRegex(ValidationError, "fingerprint"):
            control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        state = Path(self.config["registry_root"]) / self.manifest["session_id"]
        self.assertTrue((state / "PRESTART_REJECT.json").is_file())
        self.assertFalse((state / "START.json").exists())

    def test_existing_app_PID_rejects_before_install_and_never_stops_it(self):
        fake = FakeAdb(self.manifest, active_pid=True)
        with self.assertRaisesRegex(ValidationError, "existing app process"):
            control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        self.assertFalse(any(command[0] == "install" for command in fake.calls))
        self.assertFalse(any("force-stop" in command or "kill" in command for command in fake.calls))

    def assert_pid_rejection_preserves_device_and_has_no_START(self, fake):
        with mock.patch("subprocess.run", side_effect=AssertionError("physical command executed")):
            with self.assertRaisesRegex(ValidationError, "existing app process|PID lookup failed"):
                control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        self.assertFalse(any(command[0] == "install" for command in fake.calls))
        self.assertFalse(any("force-stop" in command or "kill" in command for command in fake.calls))
        state = Path(self.config["registry_root"]) / self.manifest["session_id"]
        self.assertFalse((state / "START.json").exists())
        self.assertEqual(fake.actual_calls, 0)

    def test_existing_model_probe_process_rejects_before_install_or_START(self):
        self.assert_pid_rejection_preserves_device_and_has_no_START(FakeAdb(self.manifest,
            pid_outputs={control.PACKAGE + ":model_probe": b"24680\n"}))

    def test_existing_a24_preparation_process_rejects_before_install_or_START(self):
        self.assert_pid_rejection_preserves_device_and_has_no_START(FakeAdb(self.manifest,
            pid_outputs={control.PACKAGE + ":a24_preparation": b"13579\n"}))

    def test_three_empty_process_queries_precede_install(self):
        fake = FakeAdb(self.manifest)
        with mock.patch("subprocess.run", side_effect=AssertionError("physical command executed")):
            control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        queried = [command for command in fake.calls if command[:2] == ("shell", "pidof")]
        self.assertEqual(queried, [("shell", "pidof", name) for name in control.APP_PROCESS_NAMES])
        first_install = next(i for i, command in enumerate(fake.calls) if command[0] == "install")
        self.assertTrue(all(fake.calls.index(command) < first_install for command in queried))
        self.assertEqual(fake.actual_calls, 0)

    def test_malformed_suffix_pid_output_is_not_treated_as_absent_owner(self):
        self.assert_pid_rejection_preserves_device_and_has_no_START(FakeAdb(self.manifest,
            pid_outputs={control.PACKAGE + ":a24_preparation": b"UNKNOWN_PERMISSION_DENIED\n"}))

    def test_suffix_pid_lookup_command_error_is_fail_closed(self):
        self.assert_pid_rejection_preserves_device_and_has_no_START(FakeAdb(self.manifest,
            pid_error_process=control.PACKAGE + ":model_probe"))

    def test_invalid_pid_encoding_zero_negative_and_nonbyte_are_rejected(self):
        for payload in (b"\xff", b"0", b"-1", b"123 error", "123", None):
            fake = FakeAdb(self.manifest,pid_outputs={control.PACKAGE + ":a24_preparation": payload})
            with self.subTest(payload=repr(payload)), self.assertRaisesRegex(ValidationError,"PID lookup failed"):
                control.require_no_app_process_owner(fake)
            self.assertFalse(any(command[0] == "install" for command in fake.calls))
        self.assertFalse(Path(self.config["registry_root"]).exists())

    def test_process_guard_matches_all_declared_apk_activity_processes(self):
        import xml.etree.ElementTree as ET
        source = Path(control.__file__).parents[1] / "benchmark-runner/src/modelProbe/AndroidManifest.xml"
        declared = {control.PACKAGE + activity.attrib["{http://schemas.android.com/apk/res/android}process"]
                    for activity in ET.parse(source).getroot().findall("application/activity")}
        self.assertEqual(set(control.APP_PROCESS_NAMES), {control.PACKAGE, *declared})

    def test_existing_host_owner_rejects_before_install(self):
        marker = self.root / "old-owner.marker"
        marker.write_bytes(b"ORIGINAL_OWNER_PRESERVED")
        self.config["existing_owner_files"] = [str(marker)]
        fake = FakeAdb(self.manifest)
        with self.assertRaisesRegex(ValidationError, "host owner"):
            control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        self.assertFalse(any(command[0] == "install" for command in fake.calls))
        self.assertEqual(marker.read_bytes(), b"ORIGINAL_OWNER_PRESERVED")

    def test_unregistered_model_target_never_constructs_native_client(self):
        self.manifest["models"]["D_CPU"]["target"]["gpu_driver"] = None
        with mock.patch.object(control, "NativeAdbClient", side_effect=AssertionError("native device client constructed")):
            with self.assertRaisesRegex(ValidationError, "manifest bytes contain different settings|DEVICE_UNVERIFIED"):
                control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True)

    def rewrite_source_fixture_manifest(self):
        path = Path(self.config["source_code_manifest"])
        path.write_text(json.dumps(self.source_manifest),encoding="utf-8")
        self.config["source_code_sha256"] = sha256(path)
        self.auth["source_code_sha256"] = sha256(path)

    def assert_source_rejected_before_native_client_or_registry(self, reason):
        with mock.patch.object(control,"NativeAdbClient",side_effect=AssertionError("native client constructed")), \
             mock.patch("subprocess.run",side_effect=AssertionError("physical command executed")):
            with self.assertRaisesRegex(ValidationError,reason):
                control.run_one(self.manifest,self.config,self.auth,self.gate,execute_authorized=True)
        self.assertFalse(Path(self.config["registry_root"]).exists())

    def test_source_root_is_required_before_any_native_client_or_registry(self):
        self.config.pop("source_root")
        self.assert_source_rejected_before_native_client_or_registry("source_root missing")

    def test_changed_source_entry_is_rejected_even_when_manifest_bytes_match(self):
        self.fixture_source.write_bytes(b"CHANGED_CURRENT_SOURCE")
        self.assert_source_rejected_before_native_client_or_registry("current source bytes/SHA differ")

    def test_missing_source_entry_is_rejected_before_any_native_client(self):
        self.fixture_source.unlink()
        self.assert_source_rejected_before_native_client_or_registry("artifact missing")

    def test_duplicate_case_insensitive_source_entries_are_rejected(self):
        self.source_manifest["files"].append({**self.source_manifest["files"][0],"path":"TOOLS/D1_A24_LAPTOP_CONTROL.PY"})
        self.rewrite_source_fixture_manifest()
        self.assert_source_rejected_before_native_client_or_registry("duplicate or missing source path")

    def test_unsafe_source_path_is_rejected_before_native_client(self):
        self.source_manifest["files"][1]["path"] = "../outside.py"
        self.rewrite_source_fixture_manifest()
        self.assert_source_rejected_before_native_client_or_registry("unsafe artifact path")

    def test_controller_cannot_be_omitted_from_authorized_source_manifest(self):
        self.source_manifest["files"] = self.source_manifest["files"][1:]
        self.rewrite_source_fixture_manifest()
        self.assert_source_rejected_before_native_client_or_registry("controller is absent")

    def test_source_list_cannot_bind_different_executing_controller_bytes(self):
        self.fixture_controller.write_bytes(b"DIFFERENT_CONTROLLER_NOT_EXECUTED")
        self.source_manifest["files"][0].update(bytes=self.fixture_controller.stat().st_size,
                                                sha256=sha256(self.fixture_controller))
        self.rewrite_source_fixture_manifest()
        self.assert_source_rejected_before_native_client_or_registry("actual executing controller bytes")

    def test_empty_or_wrong_schema_source_manifest_is_rejected(self):
        self.source_manifest["files"] = []
        self.rewrite_source_fixture_manifest()
        self.assert_source_rejected_before_native_client_or_registry("has no file entries")
        self.source_manifest["schema"] = "OLD_SOURCE_SCHEMA"
        self.rewrite_source_fixture_manifest()
        self.assert_source_rejected_before_native_client_or_registry("schema mismatch")

    def test_source_symlink_or_reparse_refusal_precedes_native_client(self):
        original = control.contained_file
        def refused_source(root,relative):
            if root.resolve() == self.source_root.resolve():
                raise ValidationError("symlink/reparse artifact: SOFTWARE_MOCK_SOURCE")
            return original(root,relative)
        with mock.patch.object(control,"contained_file",side_effect=refused_source):
            self.assert_source_rejected_before_native_client_or_registry("symlink/reparse")

    def test_source_root_must_contain_the_actual_controller_repository_path(self):
        other = self.root / "wrong_repository";other.mkdir()
        self.config["source_root"] = str(other)
        self.assert_source_rejected_before_native_client_or_registry("does not contain")

    def test_fake_bad_recovered_trace_records_FAIL_and_no_retry(self):
        fake = FakeAdb(self.manifest, corrupt=True)
        with self.assertRaises(ValidationError):
            control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        state = Path(self.config["registry_root"]) / self.manifest["session_id"]
        self.assertTrue((state / "FAIL.json").is_file())
        self.assertFalse((state / "COMPLETE.json").exists())

    def assert_failed_completion_has_no_COMPLETE(self, fake, reason):
        with mock.patch("subprocess.run", side_effect=AssertionError("physical command executed")):
            with self.assertRaisesRegex(ValidationError, reason):
                control.run_one(self.manifest, self.config, self.auth, self.gate, execute_authorized=True, client=fake)
        state = Path(self.config["registry_root"]) / self.manifest["session_id"]
        self.assertTrue((state / "START.json").exists())
        self.assertTrue((state / "FAIL.json").exists())
        self.assertFalse((state / "COMPLETE.json").exists())
        self.assertTrue((state / "host_hal_partial.jsonl").exists())
        self.assertEqual(fake.actual_calls, 0)
        self.assertEqual(sum(command[0] == "install" for command in fake.calls), 1)

    def test_summary_does_not_trigger_recovery_before_delayed_cleanup(self):
        fake = FakeAdb(self.manifest,cleanup_delay_ns=20*NS)
        with mock.patch("subprocess.run", side_effect=AssertionError("physical command executed")):
            result = control.run_one(self.manifest,self.config,self.auth,self.gate,execute_authorized=True,client=fake)
        self.assertEqual(result["status"],"COMPLETE_TRACE_RECOVERED")
        self.assertGreaterEqual(fake.cleanup_observed_at-fake.origin,230*NS)
        cleanup_reads = [i for i,command in enumerate(fake.calls) if command[-1].endswith("cleanup.json")]
        recovery = next(i for i,command in enumerate(fake.calls) if "tar" in command)
        self.assertGreater(recovery,max(cleanup_reads))
        complete = control.load_json(Path(self.config["registry_root"])/self.manifest["session_id"]/"COMPLETE.json")
        self.assertFalse(complete["journal_final_fsync_close_observed"])

    def test_cleanup_failure_records_FAIL_despite_successful_summary(self):
        self.assert_failed_completion_has_no_COMPLETE(FakeAdb(self.manifest,cleanup_failed=True),"cleanup failed")

    def test_failed_summary_records_FAIL_without_COMPLETE(self):
        self.assert_failed_completion_has_no_COMPLETE(FakeAdb(self.manifest,summary_status="FAILED"),"app summary")

    def test_failure_artifact_records_FAIL_without_COMPLETE(self):
        self.assert_failed_completion_has_no_COMPLETE(FakeAdb(self.manifest,failure_evidence=True),"app failure artifact")

    def test_cleanup_timeout_records_FAIL_without_restarting_the_measurement(self):
        self.assert_failed_completion_has_no_COMPLETE(FakeAdb(self.manifest,cleanup_delay_ns=1_000*NS),"cleanup timeout")

    def test_recovered_cleanup_cannot_differ_from_observed_success(self):
        self.assert_failed_completion_has_no_COMPLETE(FakeAdb(self.manifest,archive_cleanup_failed=True),"terminal artifacts differ")

    def test_raw_HAL_retains_clock_brackets_and_unknown_cache(self):
        sample = control.read_hal(FakeAdb(self.manifest))
        self.assertGreaterEqual(sample["device_elapsed_after_ns"], sample["device_elapsed_before_ns"])
        self.assertIsNone(sample["sensors"][0]["cache_age_ns"])
        self.assertFalse(sample["independent_sample_claim"])

    def test_cached_AP_cannot_replace_current_HAL_AP(self):
        fake = FakeAdb(self.manifest)
        original = fake.command
        def command(*args, **kwargs):
            if args == ("shell", "dumpsys", "thermalservice"):
                return b"Cached temperatures:\nTemperature{mValue=99.0, mType=0, mName=MOCK_AP, mStatus=0}\nCurrent temperatures from HAL:\nTemperature{mValue=30.0, mType=0, mName=MOCK_AP, mStatus=0}\nCurrent cooling devices from HAL:\n"
            return original(*args, **kwargs)
        fake.command = command
        sample = control.read_hal(fake)
        self.assertEqual([s["value_c"] for s in sample["sensors"]], [30.0])
        self.assertEqual(sample["sensor_source_section"],"CURRENT_HAL")

    def test_user_SOC10_contract_is_named_and_does_not_change_legacy(self):
        control.frozen_gate(self.gate)
        altered = {**self.gate,"minimum_SOC_percent":10,"maximum_SOC_percent":100}
        with self.assertRaises(ValidationError): control.frozen_gate(altered)
        control.frozen_gate({**altered,"soc_contract":"USER_SOC_GE10_20261015"})

    def test_isolated_package_requires_exact_authorization_and_target_binding(self):
        package=control.ISOLATED_PACKAGE
        self.config['package_name']=package
        self.config['apk_identity']['package']=package
        for model in self.manifest['models'].values(): model['target']['package_name']=package
        path=self.root/'bundle/session_manifest.json';path.write_text(json.dumps(self.manifest),encoding='utf-8')
        self.config.update(manifest_bytes=path.read_bytes(),manifest_sha256=sha256(path),
            files=[{'path':'session_manifest.json','bytes':path.stat().st_size,'sha256':sha256(path)}])
        self.auth['manifest_sha256']=self.config['manifest_sha256']
        with self.assertRaisesRegex(ValidationError,'isolated package is not explicitly authorized'):
            control.check_authorization(self.manifest,self.config,self.auth,self.gate,execute_authorized=True)
        self.auth['package_name']=package
        control.check_authorization(self.manifest,self.config,self.auth,self.gate,execute_authorized=True)
        self.config['package_name']='com.example.unrelated'
        with self.assertRaisesRegex(ValidationError,'unapproved measurement package'):
            control.check_authorization(self.manifest,self.config,self.auth,self.gate,execute_authorized=True)

    def test_verified_installed_exact_APK_does_not_reinstall(self):
        fake=FakeAdb(self.manifest);original=fake.command
        def command(*args,**kwargs):
            if args==('shell','pm','path',control.PACKAGE):return b'package:/data/app/OUR/base.apk\n'
            if args==('shell','sha256sum','/data/app/OUR/base.apk'):return (self.config['apk']['sha256']+'  /data/app/OUR/base.apk\n').encode()
            return original(*args,**kwargs)
        fake.command=command;self.config['reuse_verified_installed_APK']=True
        control.run_one(self.manifest,self.config,self.auth,self.gate,execute_authorized=True,client=fake)
        self.assertFalse(any(call[0]=='install' for call in fake.calls))

    def test_absent_isolated_APK_is_installed_before_session_start(self):
        fake=FakeAdb(self.manifest);original=fake.command
        def command(*args,**kwargs):
            if args==('shell','pm','path',control.PACKAGE):
                self.assertEqual(kwargs['accepted_codes'],(0,1))
                self.assertTrue(kwargs['reject_stderr'])
                fake.calls.append(args)
                return b''
            return original(*args,**kwargs)
        fake.command=command;self.config['reuse_verified_installed_APK']=True
        result=control.run_one(self.manifest,self.config,self.auth,self.gate,execute_authorized=True,client=fake)
        self.assertEqual(result['status'],'COMPLETE_TRACE_RECOVERED')
        install=next(i for i,c in enumerate(fake.calls) if c[0]=='install')
        start=next(i for i,c in enumerate(fake.calls) if c[:3]==('shell','am','start'))
        self.assertLess(install,start)

    def test_android_exec_out_missing_file_stdout_is_not_a_failure_artifact(self):
        fake=FakeAdb(self.manifest);original=fake.command
        def command(*args,**kwargs):
            if args[-1].endswith('failure.json'):
                return ('cat: '+args[-1]+': No such file or directory\n').encode()
            return original(*args,**kwargs)
        fake.command=command
        r=control.run_one(self.manifest,self.config,self.auth,self.gate,execute_authorized=True,client=fake)
        self.assertEqual(r['status'],'COMPLETE_TRACE_RECOVERED')
        self.assertFalse((Path(self.config['registry_root'])/self.manifest['session_id']/'FAIL.json').exists())

    def test_android_exec_out_permission_text_is_not_assumed_missing(self):
        fake=FakeAdb(self.manifest);original=fake.command
        def command(*args,**kwargs):
            if args[-1].endswith('failure.json'):return ('cat: '+args[-1]+': Permission denied\n').encode()
            return original(*args,**kwargs)
        fake.command=command
        with self.assertRaisesRegex(ValidationError,'malformed published app terminal artifact'):
            control.run_one(self.manifest,self.config,self.auth,self.gate,execute_authorized=True,client=fake)

    def test_final_journal_close_is_observed_before_complete_recovery(self):
        fake=FakeAdb(self.manifest,closure_delay_ns=20*NS)
        self.config['require_journal_closed_before_recovery']=True
        r=control.run_one(self.manifest,self.config,self.auth,self.gate,execute_authorized=True,client=fake)
        self.assertEqual(r['status'],'COMPLETE_TRACE_RECOVERED')
        self.assertGreaterEqual(fake.tar_observed_at,fake.origin+230*NS)
        ledger=Path(self.config['registry_root'])/self.manifest['session_id']/'COMPLETE.json'
        self.assertTrue(json.loads(ledger.read_text())['journal_final_fsync_close_observed'])

    def test_missing_final_journal_close_cannot_make_COMPLETE(self):
        fake=FakeAdb(self.manifest,closure_delay_ns=100*NS)
        self.config['require_journal_closed_before_recovery']=True
        with self.assertRaisesRegex(ValidationError,'journal closure timeout'):
            control.run_one(self.manifest,self.config,self.auth,self.gate,execute_authorized=True,client=fake)
        self.assertFalse((Path(self.config['registry_root'])/self.manifest['session_id']/'COMPLETE.json').exists())

    def test_tar_link_and_traversal_refused_before_any_output(self):
        for malicious in ("../outside.txt", "files/a24_laptop_results/OTHER/a.txt"):
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode="w") as archive:
                info = tarfile.TarInfo(malicious)
                info.size = 1
                archive.addfile(info, io.BytesIO(b"x"))
            destination = self.root / "unsafe-extraction"
            with self.assertRaises(ValidationError):
                control.safe_extract(stream.getvalue(), destination, session_id=self.manifest["session_id"], maximum_bytes=100)
            self.assertFalse(destination.exists())

    def test_perfetto_is_device_unverified_until_exact_cli_and_profile_bound(self):
        self.manifest["perfetto"] = "ON"
        manifest_file = self.root / "bundle/session_manifest.json"
        manifest_file.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.config.update({"manifest_bytes": manifest_file.read_bytes(), "manifest_sha256": sha256(manifest_file),
                            "files": [{"path": "session_manifest.json", "bytes": manifest_file.stat().st_size, "sha256": sha256(manifest_file)}]})
        self.auth["manifest_sha256"] = self.config["manifest_sha256"]
        with self.assertRaisesRegex(ValidationError, "DEVICE_UNVERIFIED"):
            control.check_authorization(self.manifest, self.config, self.auth, self.gate, execute_authorized=True)

    def test_confirm_cannot_skip_development_and_independent_freeze(self):
        self.manifest["stage"] = "CONFIRM"
        manifest_file = self.root / "bundle/session_manifest.json"
        manifest_file.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.config.update({"manifest_bytes": manifest_file.read_bytes(), "manifest_sha256": sha256(manifest_file),
                            "files": [{"path": "session_manifest.json", "bytes": manifest_file.stat().st_size, "sha256": sha256(manifest_file)}]})
        self.auth["manifest_sha256"] = self.config["manifest_sha256"]
        with self.assertRaisesRegex(ValidationError, "CONFIRM forbidden"):
            control.check_authorization(self.manifest, self.config, self.auth, self.gate, execute_authorized=True)

    def test_perfetto_mock_detach_is_bounded_and_stops_only_its_unique_key(self):
        class PerfettoFake:
            def __init__(self): self.calls = []
            def command(self, *args, **kwargs):
                self.calls.append(args)
                if args[-1] == "--version": return b"SOFTWARE_MOCK_PERFETTO_VERSION"
                if args == ("shell","perfetto","--help","2>&1"):
                    self.help_codes = kwargs['accepted_codes']
                    return b"--detach --attach --stop"
                if args[:2] == ("exec-out", "cat"): return b"MOCK_TRACE_BYTES_NOT_DEVICE_DATA"
                return b""
        fake = PerfettoFake()
        trace = control.start_perfetto(fake, self.manifest["session_id"], {"device_version": "SOFTWARE_MOCK_PERFETTO_VERSION", "profile_path": "SOFTWARE_MOCK_NOT_EXECUTED.pbtxt"})
        self.assertEqual(trace["hard_duration_ms"], 210000)
        self.assertEqual(fake.help_codes,(0,1))
        result = control.finish_perfetto(fake, trace)
        self.assertIsNone(result["hardware_counter_values"])
        self.assertTrue(any("--attach=" + trace["key"] in command for command in fake.calls))
        self.assertFalse(any("killall" in command for command in fake.calls))

    def test_perfetto_profile_statically_has_observation_only_and_hard_bounds(self):
        profile = Path(control.__file__).parent / "perfetto/a24_laptop_instrumentation_v1.pbtxt"
        text = profile.read_text(encoding="utf-8")
        self.assertIn("duration_ms: 210000", text)
        self.assertIn("max_file_size_bytes: 67108864", text)
        self.assertIn('ftrace_events: "sched/sched_switch"', text)
        self.assertIn('ftrace_events: "power/cpu_frequency"', text)
        self.assertNotIn("gpu_counter", text)


if __name__ == "__main__":
    unittest.main()
