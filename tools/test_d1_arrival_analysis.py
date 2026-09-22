import json
from pathlib import Path
import tempfile
import unittest

from tools.d1_arrival_analysis import session_metrics


class ArrivalAnalysisTest(unittest.TestCase):
    def test_failed_and_late_requests_remain_in_arrival_denominators(self):
        with tempfile.TemporaryDirectory() as directory:
            artifacts = Path(directory) / "artifacts"
            artifacts.mkdir()
            def success(request_id, priority, completion, deadline):
                return dict(request_id=request_id, priority=priority, terminal_status="succeeded",
                            scheduled_arrival_ns=0, actual_arrival_ns=0, queue_entry_ns=0,
                            execution_start_ns=0, output_ready_ns=completion - 2,
                            persist_complete_ns=completion, worker_release_ns=completion + 1,
                            completion_ns=completion, deadline_ns=deadline,
                            response_ns=completion, late_success=completion > deadline)
            rows = [success("u0", "urgent", 10, 20),
                    dict(request_id="u1", priority="urgent", terminal_status="failed",
                         scheduled_arrival_ns=0, terminal_ns=12),
                    success("n0", "normal", 30, 20),
                    success("n1", "normal", 15, 20)]
            (artifacts / "requests.json").write_text(json.dumps(rows))
            (artifacts / "summary.json").write_text(json.dumps(dict(session_id="s", status="incomplete",
                workload_start_ns=0, request_count=4, arrival_lag_exceeded=0)))
            entry = dict(index=0, session_id="s", kind="burst", urgent_task="classification",
                         replicate=0, pair_id="p", policy="CPU_FIFO", request_count=4)
            metrics = session_metrics(entry, Path(directory))
            self.assertEqual(metrics["urgent_deadline_miss_rate"], 0.5)
            self.assertEqual(metrics["normal_on_time_rate"], 0.5)
            self.assertEqual(metrics["completion_rate"], 0.75)
            self.assertEqual(metrics["terminal_counts"]["failed"], 1)


if __name__ == "__main__":
    unittest.main()
