import importlib.util
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("d1_logger_v4.py")
SPEC = importlib.util.spec_from_file_location("d1_logger_v4", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
LOGGER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LOGGER)


class D1LoggerV4Test(unittest.TestCase):
    def test_existing_galaxy_a24_aliases(self):
        text = """Thermal Status: 2
Current temperatures from HAL:
 Temperature{mValue=40.1, mType=0, mName=AP, mStatus=1}
 Temperature{mValue=35.2, mType=3, mName=SKIN, mStatus=0}
 Temperature{mValue=33.3, mType=2, mName=BAT, mStatus=0}
 Temperature{mValue=38.4, mType=0, mName=PATHM, mStatus=0}
Current cooling devices from HAL:
"""
        self.assertEqual(
            LOGGER.parse_thermalservice(text),
            {
                "AP": "40.1",
                "SKIN": "35.2",
                "BAT": "33.3",
                "PA": "38.4",
                "thermal_status": "2",
            },
        )

    def test_gpu_file_sequence_validation(self):
        events = [
            {"run_id": "r", "runner_session_id": "s", "sequence": 0, "event": "run_metadata"},
            {"run_id": "r", "runner_session_id": "s", "sequence": 1, "event": "inference"},
            {
                "run_id": "r",
                "runner_session_id": "s",
                "sequence": 2,
                "event": "file_summary",
                "file_event_count": 3,
                "sequence_last": 2,
            },
        ]
        LOGGER.validate_gpu_file(events, "r", "s")
        events[1]["sequence"] = 9
        with self.assertRaises(ValueError):
            LOGGER.validate_gpu_file(events, "r")

    def test_logcat_eof_stops_capture_as_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession(
                "adb", None, Path(directory), 1.0, False, Path("config")
            )
            session.consume_logcat([])
            self.assertTrue(session.stop.is_set())
            self.assertIn("stdout EOF", session.capture_error)

    def test_footerless_capture_uses_fallback_discovery(self):
        class Session(LOGGER.CaptureSession):
            def __init__(self, root):
                super().__init__("adb", None, root, 1.0, False, Path("config"))
                self.pulled = []

            def discover_runner_paths(self):
                return [
                    "/storage/emulated/0/Android/data/pkg/files/runs/"
                    "gpu-events-run-a-session-b.jsonl"
                ]

            def pull_runner_file(self, event):
                self.pulled.append(event)

        with tempfile.TemporaryDirectory() as directory:
            session = Session(Path(directory))
            session.run_id = "run-a"
            session.run_dir = Path(directory) / "run-a"
            session.recover_runner_files()
            self.assertEqual("session-b", session.pulled[0]["runner_session_id"])

    def test_new_run_inside_envelope_is_rejected(self):
        d1 = [
            {"event": "run_start", "run_id": "run-a", "mono_ns": 1},
            {"event": "run_start", "run_id": "run-b", "mono_ns": 2},
            {"event": "run_stop", "run_id": "run-a", "mono_ns": 10},
        ]
        gpu = [
            {"event": "load_start", "mono_ns": 3},
            {"event": "load_end", "mono_ns": 9},
        ]
        with self.assertRaises(ValueError):
            LOGGER.validate_run_envelope(d1, gpu, "run-a")

    def test_delegate_evidence_is_unverified_without_conclusive_phrase(self):
        evidence = LOGGER.delegate_evidence("Replacing 10 out of 10 node(s)")
        self.assertFalse(evidence["full_delegate"])
        self.assertEqual("unverified", evidence["verification"])

    def test_delegate_evidence_records_full_replacement(self):
        evidence = LOGGER.delegate_evidence(
            "Replacing 10 out of 10 node(s) with delegate, yielding one partition for the whole graph"
        )
        self.assertEqual(10, evidence["replaced_nodes"])
        self.assertEqual(10, evidence["total_nodes"])
        self.assertTrue(evidence["full_delegate"])

    def test_current_raw_is_not_calibrated(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("current_A_calibrated", source)
        self.assertNotIn("battery_power_W_signed", source)


if __name__ == "__main__":
    unittest.main()
