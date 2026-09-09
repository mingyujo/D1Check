import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("d1_thermal_dataset.py")
SPEC = importlib.util.spec_from_file_location("d1_thermal_dataset", MODULE_PATH)
assert SPEC and SPEC.loader
DATASET = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DATASET)


def thermal_record(mono_ns, ap, bat=29.0, pa=31.0, skin=28.0, **changes):
    value = {
        "schema_version": 2,
        "source": "thermalservice",
        "event": "sample",
        "run_id": "run-1",
        "mono_ns": mono_ns,
        "sampling_uncertainty_ns": 50_000_000,
        "parse_status": "ok",
        "AP": str(ap),
        "BAT": str(bat),
        "PA": str(pa),
        "SKIN": str(skin),
        "thermal_status": "0",
    }
    value.update(changes)
    return value


class ThermalDatasetTest(unittest.TestCase):
    def make_experiment(
        self,
        parent: Path,
        *,
        resource="CPU",
        formal_gpu_valid=None,
        slot_status="completed",
        validation_valid=True,
        records=None,
        slot_id="cpu-t01-d100-r001",
        order=1,
    ):
        root = parent / "experiment with spaces"
        run_id = "run-1"
        run_dir = root / "runs" / run_id
        (run_dir / "merged").mkdir(parents=True)
        (run_dir / "raw").mkdir()
        summary = {
            "schema_version": 2,
            "run_id": run_id,
            "resource": resource,
            "run_start_mono_ns": 1_000_000_000,
            "load_start_mono_ns": 3_000_000_000,
            "load_end_mono_ns": 5_000_000_000,
            "run_stop_mono_ns": 7_000_000_000,
            "run_envelope_validation": "pass",
            "thermal_coverage": {"passes_formal_requirement": True},
            "formal_gpu_valid": formal_gpu_valid,
            "inference_latency": {
                "count": 10, "mean_ms": 2.0, "median_ms": 1.9, "p95_ms": 2.5,
            },
            "duty_cycle": {
                "requested_duty_cycle_percent": 100,
                "achieved_duty_cycle_percent": 100.0,
                "actual_active_duration_ns": 2_000_000_000,
                "actual_idle_duration_ns": 0,
                "completed_inference_count": 10,
                "termination_reason": "duration_complete",
            },
            "accuracy_preflight": {"status": "not_run"},
            "energy_measurement": {"status": "raw_unverified"},
            "host_monotonic_s": -999999.0,
            "wall_ms": 9999999999999,
        }
        (run_dir / "merged" / "summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )
        if records is None:
            records = [
                thermal_record(1_100_000_000, 30.0),
                thermal_record(2_900_000_000, 30.5),
                thermal_record(3_000_000_000, 31.0),
                thermal_record(4_000_000_000, 33.0),
                thermal_record(4_900_000_000, 32.0),
                thermal_record(5_000_000_000, 31.5),
                thermal_record(6_900_000_000, 30.8),
            ]
        (run_dir / "raw" / "thermalservice.jsonl").write_text(
            "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
        )
        condition = "gpu-d100" if resource == "GPU" else "cpu-t01-d100"
        slot = {
            "slot_id": slot_id,
            "condition_id": condition,
            "block_index": 1,
            "repetition": 1,
            "order_index": order,
            "resource": resource,
            "cpu_threads": None if resource == "GPU" else 1,
            "duty_cycle_percent": 100,
            "status": slot_status,
            "attempts": 1,
            "error": (
                "CoolingTimeout: matched cooling timed out"
                if slot_status == "failed" else None
            ),
            "run_id": run_id,
            "run_dir": str(run_dir),
            "cooling": {"status": "completed"},
            "validation": {
                "valid": validation_valid,
                "checks": {
                    "resource": True,
                    "cpu_threads": True,
                    "duty_request": True,
                    "duty_period": True,
                },
            },
        }
        manifest = {
            "schema_version": 1,
            "experiment_id": "experiment-1",
            "status": "completed",
            "config": {"duration_s": 2},
            "provenance": {
                "accuracy_preflight": {"status": "not_run"},
                "energy_measurement": {"status": "raw_unverified"},
            },
            "runs": [slot],
        }
        (root / DATASET.MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        return root, manifest, summary, slot

    def test_phase_intervals_are_half_open(self):
        timestamps = {
            "run_start_mono_ns": 1,
            "load_start_mono_ns": 3,
            "load_end_mono_ns": 5,
            "run_stop_mono_ns": 7,
        }
        self.assertEqual("baseline", DATASET.classify_phase(1, timestamps)[0])
        self.assertEqual("load", DATASET.classify_phase(3, timestamps)[0])
        self.assertEqual("cooling", DATASET.classify_phase(5, timestamps)[0])
        self.assertIsNone(DATASET.classify_phase(7, timestamps))

    def test_endpoint_prefers_latest_sample_before_or_equal(self):
        samples = [
            {"mono_ns": 10, "sampling_uncertainty_ns": 1},
            {"mono_ns": 20, "sampling_uncertainty_ns": 1},
            {"mono_ns": 31, "sampling_uncertainty_ns": 1},
        ]
        selected = DATASET.select_endpoint_sample(
            samples, 30, allow_after_fallback=False, maximum_offset_ms=1
        )
        self.assertEqual(20, selected["sample_mono_ns"])
        self.assertEqual("before_or_equal", selected["selection_method"])

    def test_run_start_allows_after_fallback(self):
        samples = [{"mono_ns": 1_100_000_000, "sampling_uncertainty_ns": 10}]
        selected = DATASET.select_endpoint_sample(
            samples, 1_000_000_000, allow_after_fallback=True, maximum_offset_ms=200
        )
        self.assertEqual("after_fallback", selected["selection_method"])
        self.assertEqual(100.0, selected["signed_offset_ms"])
        self.assertEqual("ok", selected["quality"])

    def test_endpoint_over_two_seconds_is_too_far_and_value_is_not_used(self):
        sample = {"mono_ns": 1, "sampling_uncertainty_ns": 1}
        selected = DATASET.select_endpoint_sample(
            [sample], 2_100_000_002, allow_after_fallback=False, maximum_offset_ms=2000
        )
        self.assertEqual("too_far", selected["quality"])
        self.assertIsNone(selected["sample"])

    def test_invalid_and_missing_sensors_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "thermal.jsonl"
            invalid = thermal_record(1, 30)
            invalid.pop("SKIN")
            path.write_text(
                "not-json\n" + json.dumps(invalid) + "\n", encoding="utf-8"
            )
            samples, issues, count = DATASET.load_thermal_samples(path, "run-1")
        self.assertEqual(2, count)
        self.assertEqual([], samples)
        self.assertTrue(any("malformed_json" in issue for issue in issues))
        self.assertTrue(any("SKIN" in issue for issue in issues))

    def test_android_clock_domain_only_and_phase_deltas_and_peak(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(Path(directory))
            dataset = DATASET.build_dataset(root)
        ap = next(
            row for row in dataset["phase_temperature_summary"] if row["sensor"] == "AP"
        )
        self.assertEqual(1.0, ap["baseline_change_c"])
        self.assertEqual(0.5, ap["load_change_c"])
        self.assertAlmostEqual(-0.7, ap["cooling_change_c"])
        self.assertEqual(33.0, ap["load_peak_temperature_c"])
        self.assertEqual(4_000_000_000, ap["load_peak_mono_ns"])
        self.assertEqual(1.0, ap["load_peak_elapsed_s"])
        first = dataset["thermal_timeseries"][0]
        self.assertEqual(0.1, first["run_elapsed_s"])
        self.assertEqual(-1.9, first["load_relative_s"])

    def test_cpu_null_formal_gpu_valid_is_eligible(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(Path(directory))
            row = DATASET.build_dataset(root)["run_summary"][0]
        self.assertIsNone(row["formal_gpu_valid"])
        self.assertTrue(row["model_eligible"])

    def test_invalid_gpu_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(
                Path(directory), resource="GPU", formal_gpu_valid=False,
                slot_id="gpu-d100-r001",
            )
            row = DATASET.build_dataset(root)["run_summary"][0]
        self.assertFalse(row["model_eligible"])
        self.assertIn("gpu_delegate_not_formally_valid", row["exclusion_reasons"])

    def test_failed_run_inventory_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(
                Path(directory), slot_status="failed", validation_valid=False
            )
            row = DATASET.build_dataset(root)["run_summary"][0]
        self.assertFalse(row["model_eligible"])
        self.assertIn("run_status_not_completed", row["exclusion_reasons"])
        self.assertIn("validation_not_valid", row["exclusion_reasons"])
        self.assertIn("slot_failure:CoolingTimeout", row["exclusion_reasons"])

    def test_order_is_deterministic_and_duplicate_samples_are_removed(self):
        records = [
            thermal_record(1_100_000_000, 30),
            thermal_record(1_100_000_000, 31),
            thermal_record(2_900_000_000, 31),
            thermal_record(4_900_000_000, 32),
            thermal_record(6_900_000_000, 31),
        ]
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(Path(directory), records=records)
            first = DATASET.build_dataset(root)
            second = DATASET.build_dataset(root)
        self.assertEqual(first["run_summary"], second["run_summary"])
        self.assertEqual(first["thermal_timeseries"], second["thermal_timeseries"])
        keys = [(row["run_id"], row["mono_ns"]) for row in first["thermal_timeseries"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertIn("duplicate_thermal_sample_mono_ns", first["run_summary"][0]["exclusion_reasons"])

    def test_atomic_swap_failure_preserves_existing_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(Path(directory))
            exports = root / "exports"
            exports.mkdir()
            marker = exports / "known-good.txt"
            marker.write_text("preserve", encoding="utf-8")
            real_replace = DATASET.os.replace

            def controlled_replace(source, destination):
                if Path(source).name.startswith(".exports.tmp-"):
                    raise OSError("injected staging swap failure")
                return real_replace(source, destination)

            with mock.patch.object(DATASET.os, "replace", side_effect=controlled_replace):
                with self.assertRaises(OSError):
                    DATASET.export_experiment(root)
            self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    def test_reexport_has_no_duplicate_rows_and_csv_content_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(Path(directory))
            DATASET.export_experiment(root)
            first = {
                name: (root / "exports" / name).read_bytes()
                for name in (
                    "run_summary.csv", "phase_temperature_summary.csv",
                    "thermal_timeseries.csv",
                )
            }
            DATASET.export_experiment(root)
            second = {name: (root / "exports" / name).read_bytes() for name in first}
            with (root / "exports" / "thermal_timeseries.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(first, second)
        keys = [(row["run_id"], row["mono_ns"]) for row in rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_source_hash_and_sources_are_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(Path(directory))
            manifest_path = root / DATASET.MANIFEST_NAME
            thermal_path = next((root / "runs").glob("*/raw/thermalservice.jsonl"))
            before = (DATASET.sha256_file(manifest_path), DATASET.sha256_file(thermal_path))
            result = DATASET.export_experiment(root)
            after = (DATASET.sha256_file(manifest_path), DATASET.sha256_file(thermal_path))
        self.assertEqual(before, after)
        self.assertEqual(before[0], result["source_experiment_manifest_sha256"])

    def test_cli_supports_windows_path_with_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(Path(directory))
            output = io.StringIO()
            with mock.patch("sys.stdout", output):
                self.assertEqual(
                    0, DATASET.main(["--experiment-dir", str(root)])
                )
        self.assertEqual(DATASET.DATASET_SCHEMA, json.loads(output.getvalue())["dataset_schema"])

    def test_csv_row_counts_and_endpoint_offsets(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _, _, _ = self.make_experiment(Path(directory))
            result = DATASET.export_experiment(root)
            exports = root / "exports"
            counts = {}
            for filename in (
                "run_summary.csv", "phase_temperature_summary.csv", "thermal_timeseries.csv"
            ):
                with (exports / filename).open(encoding="utf-8", newline="") as stream:
                    counts[filename] = len(list(csv.DictReader(stream)))
        self.assertEqual(1, counts["run_summary.csv"])
        self.assertEqual(4, counts["phase_temperature_summary.csv"])
        self.assertEqual(7, counts["thermal_timeseries.csv"])
        self.assertEqual(counts["thermal_timeseries.csv"], result["row_counts"]["thermal_timeseries"])


if __name__ == "__main__":
    unittest.main()
