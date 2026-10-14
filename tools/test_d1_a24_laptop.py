from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import d1_a24_laptop_mock as fixture
import d1_a24_laptop_commands as commands
import d1_a24_laptop_prep as prep
import d1_a24_laptop_recover as recover
import d1_a24_laptop_validator as validator


class A24ManifestTest(unittest.TestCase):
    def test_exact_recipe_counts_and_arms(self):
        for arm in validator.ARMS:
            with self.subTest(arm=arm):
                manifest = fixture.fixture_manifest(arm)
                rows = validator.manifest_requests(manifest)
                self.assertEqual(len(rows), validator.RECIPE_COUNTS[manifest["recipe"]][0])

    def test_material_gate_does_not_accept_mock_inputs(self):
        manifest = fixture.fixture_manifest("L64_BASE")
        with self.assertRaisesRegex(validator.ValidationError, "approved"):
            validator.manifest_requests(manifest, require_materials=True)

    def test_rejects_future_arrival_rewriting(self):
        manifest = fixture.fixture_manifest("M128_BASE")
        manifest["requests"][0]["scheduled_arrival_ns"] -= 1
        with self.assertRaisesRegex(validator.ValidationError, "arrival"):
            validator.manifest_requests(manifest)

    def test_rejects_task_count_reduction(self):
        manifest = fixture.fixture_manifest("C252_CPU")
        manifest["requests"].pop()
        with self.assertRaisesRegex(validator.ValidationError, "denominator"):
            validator.manifest_requests(manifest)

    def test_rejects_deadline_tuning(self):
        manifest = fixture.fixture_manifest("L64_BASE")
        manifest["requests"][0]["deadline_ns"] += 1
        with self.assertRaisesRegex(validator.ValidationError, "deadline"):
            validator.manifest_requests(manifest)

    def test_rejects_noncanonical_identity(self):
        manifest = fixture.fixture_manifest("L64_BASE")
        manifest["session_id"] = "old-session"
        with self.assertRaisesRegex(validator.ValidationError, "UUID"):
            validator.manifest_requests(manifest)

    def test_rejects_unsupported_detector_gpu_request(self):
        manifest = fixture.fixture_manifest("M128_BASE")
        manifest["route"] = "C_CPU_D_GPU"
        with self.assertRaisesRegex(validator.ValidationError, "prescription"):
            validator.manifest_requests(manifest)

    def test_missing_profile_sha_is_not_filled_from_other_device(self):
        manifest = fixture.fixture_manifest("M128_BASE")
        manifest["nominal_profile_sha256"] = None
        with self.assertRaisesRegex(validator.ValidationError, "profile SHA"):
            validator.manifest_requests(manifest)

    def test_duplicate_request_identity_rejected(self):
        manifest = fixture.fixture_manifest("L64_BASE")
        manifest["requests"][1]["request_id"] = manifest["requests"][0]["request_id"]
        with self.assertRaisesRegex(validator.ValidationError, "duplicate"):
            validator.manifest_requests(manifest)


class A24TraceTest(unittest.TestCase):
    def setUp(self):
        self.manifest = fixture.fixture_manifest("M128_PAIR_G")
        self.events, self.rows = fixture.replay_mock(self.manifest)

    def validate(self):
        return validator.validate_events(self.manifest, self.events, self.rows)

    def test_all_supported_software_flows_without_nn(self):
        for arm in validator.ARMS:
            with self.subTest(arm=arm):
                manifest = fixture.fixture_manifest(arm)
                events, rows = fixture.replay_mock(manifest)
                result = validator.validate_events(manifest, events, rows)
                self.assertFalse(result["device_verified"])
                self.assertEqual(result["NN_calls_from_validator"], 0)
                self.assertEqual(result["metrics"]["planned"], len(manifest["requests"]))

    def test_fifo_strict_head_blocking(self):
        result = self.validate()
        order = [event["request_id"] for event in self.events if event["kind"] == "dispatch"]
        self.assertEqual(order, [row["request_id"] for row in self.manifest["requests"]])
        self.assertGreater(result["metrics"]["actual_pair_overlap_ns"], 0)

    def test_edd_differs_from_fifo_under_backlog_with_fifo_ties(self):
        manifest = fixture.fixture_manifest("M128_ORDER")
        events, rows = fixture.replay_mock(manifest)
        validator.validate_events(manifest, events, rows)
        order = [event["request_id"] for event in events if event["kind"] == "dispatch"]
        self.assertNotEqual(order, [row["request_id"] for row in manifest["requests"]])
        self.assertEqual(order[:6], ["MOCK-0000", "MOCK-0001", "MOCK-0002", "MOCK-0004", "MOCK-0005", "MOCK-0006"])

    def test_global_serial_has_no_actual_overlap(self):
        manifest = fixture.fixture_manifest("M128_BASE")
        events, rows = fixture.replay_mock(manifest)
        result = validator.validate_events(manifest, events, rows)
        self.assertEqual(result["metrics"]["actual_pair_overlap_ns"], 0)

    def test_wait_has_actual_idle_owners_and_exact_dose(self):
        manifest = fixture.fixture_manifest("M128_WAIT200")
        events, rows = fixture.replay_mock(manifest)
        result = validator.validate_events(manifest, events, rows)
        self.assertEqual(result["metrics"]["wait_count"], 16)
        self.assertEqual(result["metrics"]["wait_actual_ns"], 3_200_000_000)
        for event in events:
            if event["kind"] == "wait_start":
                self.assertTrue(event["waiting"])
                self.assertEqual(event["owners"], {"CPU": None, "GPU": None})

    def test_unfinished_does_not_disappear_from_denominator(self):
        manifest = fixture.fixture_manifest("C252_CPU")
        events, rows = fixture.replay_mock(manifest)
        result = validator.validate_events(manifest, events, rows)
        self.assertGreater(result["metrics"]["unfinished"], 0)
        self.assertEqual(result["metrics"]["C_planned"], 252)
        self.assertLess(result["metrics"]["C_on_time_rate_all_planned"], 1)

    def test_no_future_request_dispatch(self):
        event = next(event for event in self.events if event["kind"] == "arrival")
        event["scheduled_arrival_ns"] += 1
        with self.assertRaisesRegex(validator.ValidationError, "scheduled"):
            self.validate()

    def test_missing_request_result_rejected(self):
        self.rows.pop()
        with self.assertRaisesRegex(validator.ValidationError, "denominator"):
            self.validate()

    def test_result_time_forgery_rejected(self):
        self.rows[0]["output_ready_ns"] += 1
        with self.assertRaisesRegex(validator.ValidationError, "mismatch"):
            self.validate()

    def test_detection_persistence_is_not_cpu_release(self):
        event = next(event for event in self.events if event["kind"] == "persist_fsync")
        event["kind"] = "lane_available"
        with self.assertRaisesRegex(validator.ValidationError, "worker release"):
            self.validate()

    def test_persistence_readback_completed_timestamp_is_authoritative(self):
        event = next(event for event in self.events if event["kind"] == "persist_readback")
        event["completed_ns"] = event["mono_ns"] - 100
        row = next(row for row in self.rows if row["request_id"] == event["request_id"])
        row["persist_complete_ns"] = event["completed_ns"]
        self.validate()

    def test_lane_reuse_before_available_rejected(self):
        event = next(event for event in self.events if event["kind"] == "lane_available")
        event["kind"] = "sensor_sample"
        with self.assertRaisesRegex(validator.ValidationError, "lane reused"):
            self.validate()

    def test_route_replacement_is_not_allowed(self):
        event = next(event for event in self.events if event["kind"] == "dispatch")
        event["backend"] = "CPU"
        with self.assertRaisesRegex(validator.ValidationError, "route"):
            self.validate()

    def test_dispatch_stop_is_required(self):
        event = next(event for event in self.events if event["kind"] == "dispatch_stop")
        event["kind"] = "sensor_sample"
        with self.assertRaisesRegex(validator.ValidationError, "dispatch_stop"):
            self.validate()

    def test_truncated_logging_is_not_reported_as_complete_trace(self):
        event = next(event for event in self.events if event["kind"] == "logging_stop")
        event["kind"] = "sensor_sample"
        with self.assertRaisesRegex(validator.ValidationError, "trace is incomplete"):
            self.validate()

    def test_selected_but_unstarted_request_at_120_is_restored_and_unfinished(self):
        manifest = fixture.fixture_manifest("C252_CPU")
        events, rows = fixture.replay_mock(manifest)
        stop = next(event for event in events if event["kind"] == "dispatch_stop")
        ready, owners = set(), {"CPU": None, "GPU": None}
        for event in events[:events.index(stop)]:
            if event["kind"] == "queue_entry": ready.add(event["request_id"])
            elif event["kind"] == "dispatch": ready.remove(event["request_id"]); owners[event["backend"]] = event["request_id"]
            elif event["kind"] == "lane_available": owners["CPU"] = None
        request_id = min(ready)
        events.insert(events.index(stop), {"kind": "dispatch_selection_cutoff", "mono_ns": stop["mono_ns"], "captured_dispatch_ns": stop["mono_ns"],
            "planned_stop_ns": stop["mono_ns"], "request_id": request_id, "waiting": sorted(ready), "owners": owners, "session_id": manifest["session_id"]})
        for sequence, event in enumerate(events): event["sequence"] = sequence
        result = validator.validate_events(manifest, events, rows)
        self.assertGreater(result["metrics"]["unfinished"], 0)
        row = next(row for row in rows if row["request_id"] == request_id)
        self.assertIsNone(row["dispatch_ns"])
        self.assertEqual(row["terminal_status"], "UNFINISHED")

    def test_wait_on_busy_owner_rejected(self):
        manifest = fixture.fixture_manifest("M128_WAIT200")
        events, rows = fixture.replay_mock(manifest)
        event = next(event for event in events if event["kind"] == "wait_start")
        event["owners"]["CPU"] = "fake"
        with self.assertRaisesRegex(validator.ValidationError, "snapshot"):
            validator.validate_events(manifest, events, rows)

    def test_wait_timer_overshoot_is_measured_without_invented_tolerance(self):
        manifest = fixture.fixture_manifest("M128_WAIT200")
        events, rows = fixture.replay_mock(manifest)
        first_end = next(event["mono_ns"] for event in events if event["kind"] == "wait_end")
        for event in events:
            if event["mono_ns"] >= first_end:
                event["mono_ns"] += 100
        for row in rows:
            for field in validator.PHASE_FIELDS.values():
                if row.get(field) is not None and row[field] >= first_end:
                    row[field] += 100
        result = validator.validate_events(manifest, events, rows)
        self.assertEqual(result["metrics"]["wait_nominal_ns"], 3_200_000_000)
        self.assertEqual(result["metrics"]["wait_actual_ns"], 3_200_000_100)
        self.assertEqual(result["metrics"]["wait_timer_overshoot_ns"], 100)

    def test_response_is_not_available(self):
        result = self.validate()
        self.assertGreater(self.rows[0]["lane_available_ns"], self.rows[0]["output_ready_ns"])
        self.assertEqual(result["metrics"]["dispatches"], 128)

    def test_native_journal_delay_and_preparation_prefix_do_not_change_authority(self):
        t0 = self.events[0]["mono_ns"]
        self.events[0]["origin_ns"] = t0
        for event in self.events:
            field = validator.PHASE_FIELDS.get(event["kind"])
            if field and event["kind"] != "persist_readback":
                event[field] = event["mono_ns"]
            if event["kind"] == "persist_readback":
                event["completed_ns"] = event["mono_ns"]
            event["mono_ns"] += 100
        self.events[:0] = [
            {"kind": "runtime_submit", "key": "C_CPU", "mono_ns": t0 - 100, "session_id": self.manifest["session_id"]},
            {"kind": "runtime_ready", "key": "C_CPU", "mono_ns": t0 - 50, "session_id": self.manifest["session_id"]},
        ]
        for sequence, event in enumerate(self.events):
            event["sequence"] = sequence
        result = self.validate()
        self.assertEqual(result["metrics"]["planned"], 128)

    def test_classification_capture_persistence_does_not_change_response(self):
        rid = self.rows[0]["request_id"]
        output = next(event for event in self.events if event.get("request_id") == rid and event["kind"] == "output_ready")
        index = self.events.index(output)
        added = [{"kind": phase, "mono_ns": output["mono_ns"] + (i + 1) * 1_000_000, "request_id": rid, "session_id": self.manifest["session_id"]} for i, phase in enumerate(("persist_write", "persist_flush", "persist_fsync", "persist_rename", "persist_readback"))]
        self.rows[0]["persist_complete_ns"] = added[-1]["mono_ns"]
        self.events[index + 1:index + 1] = added
        self.events.sort(key=lambda event: event["mono_ns"])
        for sequence, event in enumerate(self.events):
            event["sequence"] = sequence
        result = self.validate()
        self.assertEqual(result["metrics"]["C_planned"], 96)


class A24SensorTest(unittest.TestCase):
    def samples(self):
        return [{"channel": "AP", "sensor_name": "mock-ap", "sensor_type": 0, "unit": "degC", "value": 30,
                 "sample_ns": i, "read_start_ns": i, "read_end_ns": i + 1, "reported_at_ns": i + 2, "cache_age_ns": 0} for i in (0, 10, 20, 30)]

    def cover(self, samples, **kwargs):
        return validator.window_coverage(samples, start_ns=5, end_ns=25, max_gap_ns=10, channel="AP", unit="degC", sensor_binding={"sensor_name": "mock-ap", "sensor_type": 0}, **kwargs)

    def test_no_tail_extrapolation(self):
        result = self.cover(self.samples()[:-1])
        self.assertEqual(result["status"], "BOUNDARY_NOT_BRACKETED")
        self.assertIsNone(result["value"])

    def test_gap_larger_than_frozen_limit_null(self):
        result = self.cover([self.samples()[0], self.samples()[-1]])
        self.assertEqual(result["status"], "GAP_EXCEEDS_FROZEN_LIMIT")

    def test_unknown_ap_source_is_not_battery_substituted(self):
        result = validator.window_coverage(self.samples(), start_ns=5, end_ns=25, max_gap_ns=10, channel="AP", unit="degC")
        self.assertEqual(result["status"], "AP_SENSOR_BINDING_UNVERIFIED")

    def test_battery_sensor_identity_rejected(self):
        rows = self.samples()
        rows[0]["sensor_type"] = 2
        with self.assertRaisesRegex(validator.ValidationError, "battery"):
            self.cover(rows)

    def test_units_must_match(self):
        rows = self.samples()
        rows[0]["unit"] = "milli-degC"
        with self.assertRaisesRegex(validator.ValidationError, "unit"):
            self.cover(rows)

    def test_read_timing_is_required(self):
        rows = self.samples()
        rows[0]["read_end_ns"] = 100
        with self.assertRaisesRegex(validator.ValidationError, "clock"):
            self.cover(rows)

    def test_bracketed_samples_only_validate_coverage(self):
        result = self.cover(self.samples())
        self.assertEqual(result["status"], "COVERAGE_ONLY_NOT_ENERGY_CALIBRATION")
        self.assertIsNone(result["value"])


class A24PreparationAndRecoveryTest(unittest.TestCase):
    def test_future_commands_require_exact_bindings_and_device_authorization(self):
        manifest = fixture.fixture_manifest("IDLE_RESIDENT")
        result = commands.command_plan(manifest, {})
        self.assertEqual(result["status"], "BLOCKED_DEVICE_UNVERIFIED")
        self.assertFalse(result["commands"])
        self.assertEqual(result["actual_device_commands"], 0)

    def test_future_emitter_cannot_sneak_mock_materials_into_device_workflow(self):
        manifest = fixture.fixture_manifest("M128_BASE")
        with self.assertRaisesRegex(validator.ValidationError, "approved"):
            commands.command_plan(manifest, {})

    def test_pc_environment_inspection_runs_no_external_binary(self):
        from unittest import mock
        with mock.patch("subprocess.run", side_effect=AssertionError("external binary executed")):
            result = prep.inspect_environment()
        self.assertEqual(result["actual_device_commands"], 0)
        self.assertEqual(result["NN_calls"], 0)

    def test_future_start_is_never_enabled_by_flag(self):
        for authorization in (None, True, "yes", {"approved": True}):
            with self.subTest(authorization=authorization):
                with self.assertRaisesRegex(validator.ValidationError, "DEVICE_UNVERIFIED"):
                    prep.require_future_authorization({}, authorization=authorization)

    def test_missing_preflight_assets_are_explicitly_blocked(self):
        result = prep.inspect_config({"schema": prep.CONFIG_SCHEMA, "protocol": validator.PROTOCOL, "assets": []}, Path("."))
        self.assertFalse(result["ready_for_actual_measurement"])
        self.assertTrue(result["missing_or_blocked"])
        self.assertEqual(result["actual_device_commands"], 0)

    def test_json_duplicate_keys_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.json"
            path.write_text('{"a":1,"a":2}', encoding="utf-8")
            with self.assertRaisesRegex(validator.ValidationError, "duplicate JSON"):
                validator.load_json(path)

    def test_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x.json"
            path.write_text('{"x":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(validator.ValidationError, "non-finite"):
                validator.load_json(path)

    def test_read_only_recovery_and_new_directory_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "source"
            source.mkdir()
            (source / "events.jsonl").write_bytes(b'{"software_mock":true}\n')
            manifest = {"schema": "a24-laptop-transport-v1", "files": [{"path": "events.jsonl", "sha256": validator.sha256(source / "events.jsonl"), "bytes": (source / "events.jsonl").stat().st_size}]}
            before = list(source.iterdir())
            result = recover.recover_local(source, manifest)
            self.assertFalse(result["copied"])
            self.assertEqual(before, list(source.iterdir()))
            receipt = recover.recover_local(source, manifest, base / "copy")
            self.assertTrue(receipt["copied"])
            self.assertEqual((source / "events.jsonl").read_bytes(), (base / "copy/events.jsonl").read_bytes())
            with self.assertRaisesRegex(validator.ValidationError, "new directory"):
                recover.recover_local(source, manifest, base / "copy")

    def test_recovery_rejects_traversal_and_sha_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "x").write_bytes(b"source")
            for name, digest in (("../x", "0" * 64), ("x", "0" * 64)):
                with self.subTest(name=name):
                    manifest = {"schema": "a24-laptop-transport-v1", "files": [{"path": name, "sha256": digest, "bytes": 6}]}
                    with self.assertRaises(validator.ValidationError):
                        recover.verify_local_delivery(source, manifest)

    def test_recovery_cannot_silently_omit_raw_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / "events.jsonl").write_bytes(b"{}\n")
            (source / "host_hal_raw.jsonl").write_bytes(b"{}\n")
            manifest = {"schema": "a24-laptop-transport-v1", "files": [{"path": "events.jsonl", "sha256": validator.sha256(source / "events.jsonl"), "bytes": 3}]}
            with self.assertRaisesRegex(validator.ValidationError, "every original file"):
                recover.verify_local_delivery(source, manifest)


if __name__ == "__main__":
    unittest.main()
