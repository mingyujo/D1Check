"""Synthetic source-only checks. DO NOT EXECUTE before root registration.

No archive, raw payload, network, model file or device access. Each simulator
invocation is synthetic and still needs inclusion in the eventual test budget.
Writing this file does not assert that any check has passed.
"""
from __future__ import annotations

import copy
import unittest

from timing_model import (UnsupportedContext, build_timing_candidate, context_of,
                          grouped_validate_timing, observed_ready_idle_gaps,
                          public_snapshot, reserve_dispatch)
from protocol_simulator import replay_measured_protocol, simulate_protocol

GUARD = {"durable_START_consumed": True,
         "start_id": "SYNTHETIC_TEST_ONLY_REQUIRES_ROOT_REGISTERED_TEST_RUN",
         "registration_sha256": "TEST_FIXTURE_NOT_A_REAL_REGISTRATION"}
BINDINGS = {"input_sha256": "1" * 64, "tensor_sha256": "2" * 64, "model_sha256": "3" * 64}


def request(rid, task, route, dispatch=0, stages=(100, 100, 100, 100, 100), ordinal=0, arrival=0):
    total, points = dispatch, {}
    for name, width in zip(("execution_start", "output_ready", "persist_complete", "worker_release", "lane_available"), stages):
        total += width
        points[name + "_ns"] = total
    return {"request_id": rid, "task": task, "route": route, "ordinal": ordinal,
            "priority": "U" if task == "C" else "N", "group": 0,
            "scheduled_arrival_ns": arrival, "actual_arrival_ns": arrival,
            "queue_entry_ns": arrival, "dispatch_ns": dispatch, "deadline_ns": 10000,
            "available_ns": total, "phases_ns": list(stages), "complete_vector": True,
            **points, **BINDINGS}


def session(sid, protocol="SERIAL", cohort=None, family="m8"):
    paired = protocol == "CG_DC"
    widths = (200,) * 5 if paired else (100,) * 5
    return {"session_id": sid, "cohort_id": cohort or sid, "source_family": family,
            "source_generation": "SYNTHETIC", "device": "A24", "bank": "M128",
            "compatibility": {"model_core_apk_signer_semantics": "EXPLICIT_SYNTHETIC_EQUIVALENCE"},
            "protocol": protocol, "arm": "FIFO_PAIR_CG" if paired else "FIFO_SERIAL_CG",
            "initial_ap_c": 35., "request_event_coverage": "COMPLETE",
            "service_stop_ns": 10000, "drain_stop_ns": 20000, "observation_end_ns": 20000,
            "requests": [request("c", "C", "GPU", stages=widths),
                         request("d", "D", "CPU", 0 if paired else sum(widths), stages=widths, ordinal=1)]}


def sources():
    return [session("serial_a"), session("serial_b"), session("pair_a", "CG_DC"), session("pair_b", "CG_DC")]


def public_for(source, now=0):
    return {"now_ns": now, "queue": [{"request_id": q["request_id"], "ordinal": q["ordinal"],
            "task": q["task"], "priority": q["priority"], "group": q["group"],
            "scheduled_arrival_ns": q["scheduled_arrival_ns"], "queue_entry_ns": q["queue_entry_ns"],
            "deadline_ns": q["deadline_ns"]} for q in source["requests"] if q["queue_entry_ns"] <= now],
            "owners": [], "initial_ap_c": source["initial_ap_c"], "history": {}}


def action_for(source, q):
    context, _ = context_of(source, q)
    return {"request_id": q["request_id"], "task": q["task"], "route": q["route"], "context": context}


def simulate(template, model, policy="FIFO_PAIR_CG", **options):
    return simulate_protocol(template, model, policy, execution_guard=GUARD,
                             redispatch_mode="ZERO_EXPLICIT_BASELINE", zero_baseline_id="SYNTHETIC_IDEAL_ZERO_COMPARATOR",
                             **options)


class ProtocolTimingSourceTests(unittest.TestCase):
    def test_whole_vector_and_task_response_boundaries(self):
        source = session("a")
        model = build_timing_candidate([source])
        state = public_for(source)
        for q in source["requests"]:
            action = action_for(source, q)
            lock = reserve_dispatch([action], state, "SERIAL")
            draw = model.draw(action, state, "SERIAL", lock, [q["ordinal"]])
            self.assertEqual(tuple(draw["stages_ns"]), (100,) * 5)
            self.assertEqual(draw["offsets_ns"]["response"], 200 if q["task"] == "C" else 300)
            self.assertEqual(draw["offsets_ns"]["lane_available"], 500)

    def test_future_actual_overlap_never_selects_pool(self):
        source = session("a")
        model = build_timing_candidate(sources())
        state = public_for(source)
        action = action_for(source, source["requests"][0])
        lock = reserve_dispatch([action], state, "SERIAL")
        a = model.draw(action, state, "SERIAL", lock, ["same_potential"])
        contaminated = copy.deepcopy(state)
        contaminated["future_actual_overlap"] = "CG_DC"
        contaminated["hidden_remaining_duration_ns"] = 100000
        b = model.draw(action, contaminated, "SERIAL", lock, ["same_potential"])
        self.assertEqual(a["sample_id"], b["sample_id"])
        self.assertEqual(a["selection"], b["selection"])
        self.assertNotIn("hidden_remaining_duration_ns", public_snapshot(contaminated))

    def test_future_queue_rejected(self):
        source = session("a")
        state = public_for(source)
        state["queue"][0]["queue_entry_ns"] = 1
        with self.assertRaises(ValueError):
            public_snapshot(state)

    def test_pair_reservation_is_before_draw_and_immutable(self):
        source = session("a")
        model = build_timing_candidate(sources())
        state = public_for(source)
        actions = [action_for(source, q) for q in source["requests"]]
        lock = reserve_dispatch(actions, state, "CG_DC")
        a = model.draw(actions[0], state, "CG_DC", lock, [0])
        self.assertEqual(a["protocol"], "CG_DC")
        self.assertEqual(tuple(a["stages_ns"]), (200,) * 5)
        state["now_ns"] = 1
        with self.assertRaises(ValueError):
            model.draw(actions[1], state, "CG_DC", lock, [1])

    def test_serial_reservation_cannot_silently_join_pair(self):
        source = session("a")
        state = public_for(source)
        state["owners"] = [{"request_id": "running", "task": "C", "route": "GPU", "dispatch_ns": 0}]
        with self.assertRaises(UnsupportedContext):
            reserve_dispatch([action_for(source, source["requests"][1])], state, "SERIAL")

    def test_ready_idle_gap_and_unknown_are_distinct(self):
        source = session("a")
        source["requests"][1] = request("d", "D", "CPU", dispatch=750, ordinal=1)
        gaps, unknown = observed_ready_idle_gaps(source)
        self.assertFalse(unknown)
        self.assertEqual(gaps[1]["ready_ns"], 500)
        self.assertEqual(gaps[1]["gap_ns"], 250)
        source.pop("request_event_coverage")
        gaps, unknown = observed_ready_idle_gaps(source)
        self.assertFalse(gaps)
        self.assertTrue(unknown)

    def test_zero_requires_explicit_registered_baseline(self):
        source = session("a")
        model = build_timing_candidate([source])
        action = {**action_for(source, source["requests"][0]), "protocol": "SERIAL"}
        with self.assertRaises(ValueError):
            model.redispatch(action, public_for(source), [0], mode="ZERO_EXPLICIT_BASELINE")
        source["request_event_coverage"] = "UNKNOWN"
        unknown_model = build_timing_candidate([source])
        result = unknown_model.redispatch(action, public_for(source), [0])
        self.assertIsNone(result["delay_ns"])

    def test_queue_wait_is_not_service(self):
        source = session("a")
        source["requests"] = [request("c", "C", "GPU", dispatch=1000)]
        model = build_timing_candidate([source])
        self.assertEqual(sum(model.samples[0]["stages_ns"]), 500)
        self.assertEqual(model.gaps[0]["gap_ns"], 1000)

    def test_missing_binding_excluded_and_retained_in_ledger(self):
        source = session("a")
        source["requests"][0].pop("input_sha256")
        model = build_timing_candidate([source])
        self.assertFalse(any(s["task"] == "C" for s in model.samples))
        self.assertTrue(any("input_sha256" in str(row["reason"]) for row in model.ledger))

    def test_bank_transfer_is_explicit_and_flags_extrapolation(self):
        source = session("a")
        template = copy.deepcopy(source)
        template["bank"] = "UNMEASURED_ARRIVAL_PATTERN"
        with self.assertRaises(UnsupportedContext):
            simulate(template, build_timing_candidate(sources()), concurrency_mode="SERIAL_INDEPENDENT")
        transferred = build_timing_candidate(sources(), bank_mode="TASK_BINDING_TRANSFER")
        result = simulate(template, transferred, concurrency_mode="SERIAL_INDEPENDENT")
        self.assertTrue(all(r["timing"]["bank_extrapolation"] for r in result["requests"]))

    def test_midexecution_join_changes_only_future_progress(self):
        template = session("new")
        template["requests"][1] = request("d", "D", "CPU", dispatch=500, ordinal=1, arrival=150)
        result = simulate(template, build_timing_candidate(sources()), concurrency_mode="DATA_DERIVED_PROGRESS")
        rows = {r["request_id"]: r for r in result["requests"]}
        self.assertEqual(rows["c"]["execution_start_ns"], 100)
        self.assertEqual(rows["d"]["dispatch_ns"], 150)
        self.assertEqual(rows["c"]["output_ready_ns"], 250)
        self.assertEqual(rows["c"]["available_ns"], 850)
        self.assertEqual(rows["d"]["available_ns"], 1000)
        self.assertTrue(any(r["public_overlap"] for r in result["rate_history"]))
        self.assertFalse(result["causal_interference_identified"])

    def test_independent_baseline_predicts_unmeasured_overlap(self):
        template = session("new")
        template["requests"][1] = request("d", "D", "CPU", dispatch=500, ordinal=1, arrival=150)
        result = simulate(template, build_timing_candidate([session("only_serial")]), concurrency_mode="SERIAL_INDEPENDENT")
        rows = {r["request_id"]: r for r in result["requests"]}
        self.assertEqual(rows["c"]["available_ns"], 500)
        self.assertEqual(rows["d"]["available_ns"], 650)
        self.assertGreater(result["metrics"]["overlap_ns"], 0)

    def test_unidentified_overlap_fallback_is_explicit(self):
        model = build_timing_candidate([session("only_serial")])
        source = session("new")
        action = action_for(source, source["requests"][0])
        with self.assertRaises(UnsupportedContext):
            model.progress_rates(action, public_for(source))
        rates = model.progress_rates(action, public_for(source), unidentified="SERIAL_INDEPENDENT")
        self.assertIn("UNIDENTIFIED", rates["evidence"])

    def test_wait_blocks_decisions_at_intervening_arrival(self):
        template = session("new")
        template.update(service_stop_ns=1_000_000_000, drain_stop_ns=2_000_000_000,
                        observation_end_ns=2_000_000_000)
        template["requests"][1] = request("d", "D", "CPU", dispatch=500, ordinal=1, arrival=100)
        result = simulate(template, build_timing_candidate(sources()), policy="FIFO_WAIT_CG", concurrency_mode="SERIAL_INDEPENDENT")
        self.assertGreaterEqual(min(r["dispatch_ns"] for r in result["requests"]), 200_000_000)
        self.assertEqual(result["wait_used_ns"], 200_000_000)

    def test_no_third_or_same_route_owner(self):
        template = session("new")
        extra = request("c2", "C", "GPU", ordinal=2)
        template["requests"].append(extra)
        result = simulate(template, build_timing_candidate(sources()), concurrency_mode="SERIAL_INDEPENDENT")
        rows = {r["request_id"]: r for r in result["requests"]}
        self.assertGreaterEqual(rows["c2"]["dispatch_ns"], rows["c"]["available_ns"])
        for decision in result["decisions"]:
            self.assertLessEqual(len(decision["public_state"]["owners"]), 2)

    def test_simulator_requires_durable_registered_start(self):
        with self.assertRaises(RuntimeError):
            simulate_protocol(session("a"), build_timing_candidate(sources()))

    def test_fixed_replay_is_arithmetic_not_predictive_pass(self):
        source = session("a")
        audit = replay_measured_protocol(source, "FIFO_SERIAL_CG")
        self.assertEqual(audit["status"], "OBSERVED_ARITHMETIC_ONLY")
        self.assertIsNone(audit["predictive_accuracy_PASS"])
        self.assertEqual(audit["new_environment_STARTs"], 0)
        source["requests"][1] = request("d", "D", "CPU", dispatch=0, ordinal=1)
        self.assertTrue(replay_measured_protocol(source)["issues"])

    def test_sparse_group_cv_retains_unvalidated_rows(self):
        result = grouped_validate_timing([session("a"), session("b")], [{"family": "m8"}], build_cap=2)
        self.assertEqual(len(result["rows"]), 4)
        self.assertTrue(all(row["status"] == "UNVALIDATED" for row in result["rows"]))
        self.assertEqual(result["parameter_fits"], 0)
        with self.assertRaises(RuntimeError):
            grouped_validate_timing([session("a"), session("b")], [{"family": "m8"}], build_cap=1)

    def test_routing_uses_target_route_public_model_identity(self):
        gpu = session("gpu")
        cpu = session("cpu")
        registry = {"C_CPU": {"model": {"sha256": "4" * 64}},
                    "C_GPU": {"model": {"sha256": "3" * 64}},
                    "D_CPU": {"model": {"sha256": "3" * 64}}}
        for source in (gpu, cpu):
            source["compatibility"] = {"public_models": registry, "public_apk_sha256": "5" * 64}
        cpu["requests"][0]["route"] = "CPU"
        cpu["requests"][0]["model_sha256"] = "4" * 64
        result = simulate(gpu, build_timing_candidate([gpu, cpu]), policy="FIFO_SERIAL_CPU",
                          concurrency_mode="SERIAL_INDEPENDENT")
        c = next(r for r in result["requests"] if r["task"] == "C")
        self.assertEqual(c["route"], "CPU")
        self.assertEqual(c["execution_context"]["model_sha256"], "4" * 64)

    def test_same_potential_is_policy_independent_for_same_support(self):
        template = session("new")
        model = build_timing_candidate(sources())
        fifo = simulate(template, model, policy="FIFO", concurrency_mode="SERIAL_INDEPENDENT")
        edd = simulate(template, model, policy="EDD", concurrency_mode="SERIAL_INDEPENDENT")
        left = {r["request_id"]: r["timing"]["selection"] for r in fifo["requests"]}
        right = {r["request_id"]: r["timing"]["selection"] for r in edd["requests"]}
        self.assertEqual(left, right)


if __name__ == "__main__":
    unittest.main()
