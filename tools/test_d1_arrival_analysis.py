import json
from pathlib import Path
import tempfile
import unittest

from tools.d1_arrival_analysis import paired_metrics, primary_kpi_svg, session_metrics


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

    def test_paired_metrics_separates_priority_and_gpu_effects(self):
        def row(policy, urgent, normal, makespan, throughput):
            return dict(pair_id="pair", kind="burst", urgent_task="classification",
                        replicate=0, policy=policy, status="completed",
                        urgent_p95_ms=urgent, urgent_deadline_miss_rate=0.0,
                        normal_mean_response_ms=normal, normal_p95_ms=normal + 10,
                        normal_on_time_rate=1.0, completion_rate=1.0,
                        makespan_s=makespan, throughput_per_s=throughput,
                        policy_compute_total_ms=2.0)
        contrasts = paired_metrics([
            row("CPU_FIFO", 1000, 500, 4.0, 2.0),
            row("CPU_URGENT", 400, 550, 4.0, 2.0),
            row("CONDITIONAL", 350, 300, 3.0, 2.5),
        ])
        self.assertEqual(len(contrasts), 3)
        by_name = {item["contrast"]: item for item in contrasts}
        self.assertEqual(by_name["CPU_URGENT-CPU_FIFO"]["urgent_p95_delta_ms"], -600)
        self.assertEqual(by_name["CONDITIONAL-CPU_URGENT"]["urgent_p95_delta_ms"], -50)
        self.assertEqual(by_name["CONDITIONAL-CPU_URGENT"]["normal_mean_response_delta_ms"], -250)

    def test_primary_kpi_svg_contains_all_policies(self):
        rows = [dict(kind="burst", urgent_task="classification", policy=policy,
                     urgent_p95_ms=value, normal_mean_response_ms=value + 1,
                     makespan_s=value / 100) for policy, value in
                zip(("CPU_FIFO", "CPU_URGENT", "CONDITIONAL"), (100, 50, 40))]
        svg = primary_kpi_svg(rows)
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(all(policy in svg for policy in ("CPU_FIFO", "CPU_URGENT", "CONDITIONAL")))


if __name__ == "__main__":
    unittest.main()
