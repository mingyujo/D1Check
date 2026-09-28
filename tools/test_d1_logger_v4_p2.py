"""P2 (2026-09-28) changes to d1_logger_v4: capture files kept open (line-buffered) instead of
open/append/close per line, and the chain-run guard on formal_npu_valid.

Byte identity with the previous per-line writer was checked once before the change on a 60,077-line
synthetic stream (the previous writer no longer exists to compare against in a test); this test pins the
content the writer must produce so a later edit cannot silently change it."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parent
ARTIFACTS = TOOLS.parent / "npu-runner" / "build" / "npu-roundtrip"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LOGGER = load("d1_logger_v4_p2_test", "d1_logger_v4.py")
RUN = "0f0f0f0f-1111-4111-8111-111111111111"


def stream_lines():
    events = [{"source": "d1check", "event": "run_start", "run_id": RUN, "mono_ns": 1000}]
    lines = ["--------- beginning of main",
             "09-28 12:00:00.000  1000  1001 I D1CHECK_EVENT: " + json.dumps(events[0])]
    for i in range(50):
        event = {"source": "gpu", "event": "inference", "run_id": RUN, "sequence": i, "note": "é ✓"}
        events.append(event)
        lines.append("09-28 12:00:01.000  4242  4243 I D1GPU   : " + json.dumps(event, ensure_ascii=False))
    lines.append("09-28 12:00:01.500  4242  4260 I tflite  : Initialized TensorFlow Lite runtime.")
    stop = {"source": "d1check", "event": "run_stop", "run_id": RUN, "mono_ns": 9999}
    events.append(stop)
    lines.append("09-28 12:00:02.000  1000  1001 I D1CHECK_EVENT: " + json.dumps(stop))
    return lines, events


class CaptureWriterTest(unittest.TestCase):
    def test_default_writer_keeps_no_handle_open(self):
        lines, events = stream_lines()
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession("adb", None, Path(directory), 1.0, False, Path("unused"))
            session._device_property = lambda name: ""
            session.recover_runner_files = lambda: None
            session.consume_logcat(lines)
            self.assertEqual({}, session._open_streams)
            raw = Path(directory, RUN, "raw", "logcat.txt").read_bytes()
            self.assertEqual(("\n".join(lines) + "\n").encode("utf-8"), raw)

    def test_capture_files_hold_exactly_the_lines_and_events(self):
        lines, events = stream_lines()
        with tempfile.TemporaryDirectory() as directory:
            session = LOGGER.CaptureSession("adb", None, Path(directory), 1.0, False, Path("unused"),
                                            keep_files_open=True)
            session._device_property = lambda name: ""
            session.recover_runner_files = lambda: None
            session.consume_logcat(lines + ["09-28 12:00:03.000  4242  4243 I D1GPU   : after stop"])
            streams = list(session._open_streams.values())
            self.assertTrue(streams)
            session.close_capture_files()
            self.assertTrue(all(stream.closed for stream in streams))
            session.close_capture_files()   # idempotent
            raw = Path(directory, RUN, "raw", "logcat.txt").read_bytes()
            self.assertEqual(("\n".join(lines) + "\n").encode("utf-8"), raw)
            jsonl = Path(directory, RUN, "raw", "logcat.jsonl").read_bytes()
            expected = "".join(json.dumps(e, ensure_ascii=False, separators=(",", ":")) + "\n" for e in events)
            self.assertEqual(expected.encode("utf-8"), jsonl)
            # appending after a close reopens and appends (thermal loop may still be running)
            session.record_thermal({"event": "sample", "mono_ns": 5000}, "probe")
            session.close_capture_files()
            thermal = Path(directory, RUN, "raw", "thermalservice.jsonl").read_text("utf-8").splitlines()
            self.assertEqual(1, len(thermal))


def case(name: str) -> Path | None:
    path = ARTIFACTS / name
    return path if (path / "roundtrip.json").is_file() else None


@unittest.skipUnless(case("npu-d100") and case("chain-m2-per-segment"), "run gradlew :npu-runner:testDebugUnitTest")
class ChainGuardTest(unittest.TestCase):
    def summary_for(self, name: str) -> dict:
        roundtrip = load("test_npu_runner_roundtrip_logger_p2", "test_npu_runner_roundtrip.py")
        with tempfile.TemporaryDirectory() as directory:
            run_dir, info, events = roundtrip.build_host_run(Path(directory), ARTIFACTS / name)
            with contextlib.redirect_stdout(io.StringIO()):
                LOGGER.analyze(run_dir)
            return json.loads((run_dir / "merged" / "summary.json").read_text("utf-8"))

    def test_chain_run_is_never_formal_and_ordinary_runs_carry_no_new_key(self):
        chain = self.summary_for("chain-m2-per-segment")
        self.assertIs(False, chain["formal_npu_conditions"]["not_chain_run"])
        self.assertIs(False, chain["formal_npu_valid"])
        ordinary = self.summary_for("npu-d100")
        self.assertNotIn("not_chain_run", ordinary["formal_npu_conditions"])


if __name__ == "__main__":
    unittest.main()
