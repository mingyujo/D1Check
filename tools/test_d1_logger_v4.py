import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("d1_logger_v4.py")
SPEC = importlib.util.spec_from_file_location("d1_logger_v4", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
LOGGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOGGER)


class D1LoggerV4Test(unittest.TestCase):
    def test_percentile_interpolates(self):
        self.assertEqual(LOGGER.percentile([10.0], 0.95), 10.0)
        self.assertAlmostEqual(LOGGER.percentile([0.0, 100.0], 0.95), 95.0)

    def test_analyze_joins_nearest_sample(self):
        run_id = "run-test"
        events = [
            {
                "run_id": run_id,
                "source": "d1check",
                "event": "sample",
                "mono_ns": 1_000_000_000,
                "thermal_status": 2,
                "current_raw": -100,
            },
            {
                "run_id": run_id,
                "source": "gpu",
                "event": "inference_end",
                "sequence": 1,
                "mono_ns": 1_100_000_000,
                "start_mono_ns": 1_080_000_000,
                "latency_ms": 20.0,
                "inference_index": 0,
                "batch_size": 1,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.jsonl"
            raw.write_text("\n".join(json.dumps(event) for event in events), encoding="utf-8")
            output = root / "analysis"
            LOGGER.analyze(raw, output, run_id)
            summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["gpu_timeline_count"], 1)
            self.assertEqual(summary["latency"]["inference_end"]["median_ms"], 20.0)
            timeline = (output / "latency_timeline.csv").read_text(encoding="utf-8-sig")
            self.assertIn("100.0", timeline)
            self.assertIn("-100", timeline)


if __name__ == "__main__":
    unittest.main()
