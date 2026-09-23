import copy
import unittest
from unittest.mock import patch

from tools import d1_arrival_timing_dev as v


def fixture():
    """Synthetic nanoseconds; no empirical data or performance prediction."""
    ticket = {"id": "u", "task": "classification", "priority": "urgent", "ordinal": 0}
    budgets = {k: dict(zip(v.ALL_FIELDS, (2, 40, 100, 10, 5) if k.endswith("CPU") else (2, 40, 250, 10, 5))) for k in v.KEYS}
    trace = {"protocol": v.PROTOCOL, "policy": v.POLICY, "estimate_contract": v.CONTRACT,
             "estimate_version": "synthetic-v1", "estimate_provenance": "PC synthetic only", "budgets": budgets,
             "capacity": 512, "clock": "elapsedRealtimeNanos", "overflow": False, "dropped_records": 0,
             "complete": True, "experiment_ready": False, "records": []}
    lanes = {b: {"phase": "AVAILABLE", "request_id": None, "task": None, "phase_since_ns": 0, "persist_since_ns": None} for b in ("CPU", "GPU")}

    def decision(time, queue):
        observed = copy.deepcopy(lanes)
        for b, lane in observed.items():
            lane["remaining_ns"], lane["remaining_state"] = v.remaining(lane, time, budgets, b)
        trace["records"].append({"seq": len(trace["records"]), "kind": "decision", "mono_ns": time,
                                 "decision_end_ns": time + 1, "queue": queue, "estimate_version": "synthetic-v1",
                                 "lanes": observed, **v.replay(queue, lanes, time, budgets)})

    def phase(time, name):
        old = lanes["CPU"]
        lanes["CPU"] = {"phase": name, "request_id": None if name == "AVAILABLE" else "u",
                        "task": None if name == "AVAILABLE" else "classification", "phase_since_ns": time,
                        "persist_since_ns": time if name == "PERSISTED" else None if name in ("ASSIGNED", "AVAILABLE") else old["persist_since_ns"]}
        trace["records"].append({"seq": len(trace["records"]), "kind": "phase", "mono_ns": time, "backend": "CPU", "request_id": "u", "phase": name})

    decision(10, [ticket])
    phase(12, "ASSIGNED")
    decision(14, [])
    phase(80, "EXECUTING")  # dispatch delay > synthetic preparation estimate
    phase(200, "OUTPUT_READY")  # actual service > synthetic estimate
    phase(210, "PERSISTED")
    phase(212, "WORKER_RELEASED")
    phase(230, "AVAILABLE")  # scheduler callback delayed beyond worker release
    decision(232, [])
    row = {"protocol": v.PROTOCOL, "session_id": "s", "request_id": "u", "task_id": "classification",
           "priority": "urgent", "ordinal": 0, "sample_id": "image", "selected_backend": "CPU", "scheduled_arrival_ns": 1,
           "actual_arrival_ns": 2, "queue_entry_ns": 3, "dispatch_ns": 12, "execution_start_ns": 80,
           "inference_start_ns": 90, "inference_end_ns": 190, "inference_ns": 100, "output_ready_ns": 200,
           "persist_complete_ns": 210, "worker_release_ns": 212, "lane_available_ns": 230,
           "terminal_status": "succeeded", "completion_ns": 200, "response_ns": 199,
           "decision_reason": "estimated_cpu_reply", "policy_evaluation_ns": 1, "policy_compute_ns": 3}
    config = {"contract": v.CONTRACT, "version": "synthetic-v1", "provenance": "PC synthetic only", "budgets": budgets}
    files = {"decision_trace.json": trace, "manifest.json": {"protocol": v.PROTOCOL, "policy": v.POLICY,
             "session_id": "s", "development_only": True, "experiment_ready": False, "timing_estimates": config,
             "requests": [{k: row[k] for k in ("request_id", "task_id", "priority", "ordinal", "sample_id")}]},
             "requests.json": [row], "u.event.json": {k: val for k, val in row.items() if k != "lane_available_ns"},
             "summary.json": {"protocol": v.PROTOCOL, "session_id": "s", "request_count": 1, "terminal_count": 1, "status": "completed"},
             "cleanup.json": {"status": "completed"}}
    return files


class TimingDevTest(unittest.TestCase):
    def test_full_in_memory_replay_and_three_distinct_boundaries(self):
        files = fixture()
        with patch.object(v, "read", side_effect=lambda path: files[path.name]):
            result = v.validate_artifacts("never-read-or-written")
        self.assertEqual((result["decisions"], result["no_selection"], result["dispatched"]), (3, 2, 1))
        self.assertFalse(result["experiment_ready"])

    def test_missing_estimates_and_overrun_are_not_zero_or_available(self):
        files = fixture()
        budgets = files["decision_trace.json"]["budgets"]
        lane = {"phase": "EXECUTING", "task": "classification", "request_id": "u", "phase_since_ns": 80, "persist_since_ns": None}
        self.assertEqual(v.remaining(lane, 181, budgets, "CPU"), (None, "UNKNOWN_OVERRUN"))
        budgets["classification_CPU"][v.FIELDS[3]] = None
        self.assertEqual(v.remaining(lane, 90, budgets, "CPU"), (None, "UNKNOWN_MISSING_BUDGET"))
        config = files["manifest.json"]["timing_estimates"]
        self.assertEqual(v.check_estimates(config)["missing_budgets"], ["classification_CPU.persist_to_lane_available_ns"])

    def test_snapshot_future_information_and_actual_decision_tampering_rejected(self):
        for mutation in (lambda t: t["records"][0]["lanes"]["CPU"].update(actual_completion_ns=200),
                         lambda t: t["records"][0]["queue"][0].update(actual_service_ns=120),
                         lambda t: t["records"][0]["selected"].update(backend="GPU"),
                         lambda t: t["records"][0].update(actual_future_arrivals=[])):
            trace = fixture()["decision_trace.json"]
            mutation(trace)
            with self.assertRaises(ValueError):
                v.validate_trace(trace)

    def test_future_ledger_cannot_change_earlier_decision(self):
        files = fixture()
        original = copy.deepcopy(v.validate_trace(files["decision_trace.json"]))
        files["requests.json"][0]["output_ready_ns"] = 9000
        self.assertEqual(v.validate_trace(files["decision_trace.json"]), original)
        with patch.object(v, "read", side_effect=lambda path: files[path.name]), self.assertRaises(ValueError):
            v.validate_artifacts("unused")

    def test_missing_transition_and_premature_availability_rejected(self):
        for remove in (1, 6):  # assignment or release, with apparently contiguous sequence
            trace = fixture()["decision_trace.json"]
            del trace["records"][remove]
            for i, row in enumerate(trace["records"]):
                row["seq"] = i
            with self.assertRaises(ValueError):
                v.validate_trace(trace)

    def test_overflow_incomplete_and_legacy_protocol_fail_closed(self):
        for change in ({"overflow": True}, {"dropped_records": 1}, {"complete": False},
                       {"protocol": "arrival-scheduler-v1"}, {"experiment_ready": True}):
            trace = fixture()["decision_trace.json"] | change
            with self.assertRaises(ValueError):
                v.validate_trace(trace)

    def test_both_busy_unknown_fallback_and_fixed_expected_numbers(self):
        trace = fixture()["decision_trace.json"]
        first = trace["records"][0]
        self.assertEqual(first["candidates"], [{"request_id": "u", "cpu_reply_ns": 142, "gpu_reply_ns": 292, "reason": "estimated_cpu_reply"}])
        lanes = copy.deepcopy(first["lanes"])
        for lane in lanes.values():
            lane.update(phase="EXECUTING", request_id="active", task="classification", phase_since_ns=10)
        self.assertEqual(v.replay(first["queue"], lanes, 200, trace["budgets"])["reason"], "wait_both_busy")
        lanes["GPU"] = first["lanes"]["GPU"]
        self.assertEqual(v.replay(first["queue"], lanes, 200, trace["budgets"])["reason"], "wait_unknown")
        lanes["CPU"] = first["lanes"]["CPU"]
        budgets = {k: dict.fromkeys(v.ALL_FIELDS) for k in v.KEYS}
        self.assertEqual(v.replay(first["queue"], lanes, 200, budgets)["reason"], "fallback_cpu_unknown")

    def test_event_ledger_release_mismatch_and_omitted_request_rejected(self):
        for mutate in (lambda f: f["requests.json"][0].update(lane_available_ns=211),
                       lambda f: f["requests.json"][0].update(selected_backend="GPU"),
                       lambda f: f["requests.json"][0].update(policy_evaluation_ns=200),
                       lambda f: f["u.event.json"].update(output_ready_ns=199),
                       lambda f: f["requests.json"].clear()):
            files = fixture()
            mutate(files)
            with patch.object(v, "read", side_effect=lambda path: files[path.name]), self.assertRaises(ValueError):
                v.validate_artifacts("unused")

    def test_omitted_null_decision_detected_even_after_renumbering(self):
        files = fixture()
        del files["decision_trace.json"]["records"][2]
        for seq, record in enumerate(files["decision_trace.json"]["records"]):
            record["seq"] = seq
        with patch.object(v, "read", side_effect=lambda path: files[path.name]), self.assertRaisesRegex(ValueError, "missing policy call"):
            v.validate_artifacts("unused")


if __name__ == "__main__":
    unittest.main()
