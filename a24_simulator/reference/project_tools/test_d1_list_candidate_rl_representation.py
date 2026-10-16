"""Pure ownership/rounding/credit algebra; no native environment or learning."""
from __future__ import annotations

import unittest
from unittest import mock

from tools.d1_list_candidate_rl_representation import SourceIntegrityError, certificate_from_ledger
from tools import d1_list_candidate_rl_representation as certificate


NS = 1_000_000_000
ORIGIN = 35 * NS


def row(rid, task, backend, arrival, dispatch, end, ordinal=0):
    return {"id": rid, "task": task, "backend": backend, "ordinal": ordinal,
            "priority": "urgent" if task == "classification" else "normal",
            "deadline_offset_ns": 1_500_000_000 if task == "classification" else 6 * NS,
            "arrival_ns": ORIGIN + round(arrival * NS), "dispatch_ns": ORIGIN + round(dispatch * NS),
            "lane_available_ns": ORIGIN + round(end * NS), "status": "succeeded"}


class ChronologicalCertificateTests(unittest.TestCase):
    def test_forced_CPU_wait_does_not_consume_discretionary_credit(self):
        value = certificate_from_ledger([row("D0", "detection", "CPU", 0, 0, 1),
                                         row("D1", "detection", "CPU", .1, 1, 2, 1)])
        self.assertEqual(value["maximum_required_discretionary_s_lower_bound"], 0)
        self.assertEqual(value["exact_schedule_outcome"], "unknown")

    def test_free_GPU_alternative_makes_CPU_resource_wait_discretionary(self):
        value = certificate_from_ledger([row("D0", "detection", "CPU", 0, 0, 1),
                                         row("C1", "classification", "GPU", .6, 1.1, 1.4, 1)])
        self.assertEqual(value["exact_schedule_outcome"], "excluded")
        self.assertGreater(value["maximum_required_discretionary_s_lower_bound"], .49999999)
        self.assertEqual(value["worst_spell"]["intermediate_actual_dispatch_count"], 0)

    def test_classification_CPU_blocks_unmeasured_classification_GPU_parallel(self):
        value = certificate_from_ledger([row("C0", "classification", "CPU", 0, 0, 1),
                                         row("C1", "classification", "GPU", .6, 1.1, 1.4, 1)])
        self.assertLess(value["maximum_required_discretionary_s_lower_bound"], .1)
        self.assertEqual(value["exact_schedule_outcome"], "unknown")

    def test_lane_release_does_not_reset_credit(self):
        value = certificate_from_ledger([row("D0", "detection", "CPU", 0, 0, 1),
                                         row("C1", "classification", "CPU", .6, 1.2, 1.5, 1)])
        self.assertEqual(value["exact_schedule_outcome"], "excluded")
        self.assertGreater(value["worst_spell"]["required_discretionary_s_lower_bound"], .59999999)

    def test_same_time_pair_does_not_double_credit(self):
        value = certificate_from_ledger([row("D0", "detection", "CPU", 0, 0, 1),
                                         row("C0", "classification", "GPU", 0, 0, .8, 1),
                                         row("C1", "classification", "GPU", .85, 1.15, 1.45, 2)])
        self.assertEqual(value["worst_spell"]["same_rounded_dispatch_group_count"], 2)
        self.assertEqual(value["exact_schedule_outcome"], "excluded")

    def test_rounding_shrink_does_not_exclude_exact_quarter_second(self):
        value = certificate_from_ledger([row("D0", "detection", "CPU", 0, 0, 1),
                                         row("C1", "classification", "GPU", .6, .85, 1.2, 1)])
        self.assertLessEqual(value["maximum_required_discretionary_s_lower_bound"], .25)
        self.assertEqual(value["exact_schedule_outcome"], "unknown")

    def test_response_or_worker_release_does_not_free_lane(self):
        first = row("C0", "classification", "CPU", 0, 0, 1)
        first.update(output_ready_ns=ORIGIN + NS // 10, worker_release_ns=ORIGIN + NS // 2)
        value = certificate_from_ledger([first, row("C1", "classification", "GPU", .6, 1.1, 1.4, 1)])
        self.assertLess(value["maximum_required_discretionary_s_lower_bound"], .1)

    def test_FIFO_head_violation_is_a_separate_negative_certificate(self):
        value = certificate_from_ledger([row("C0", "classification", "CPU", .1, 1, 1.2),
                                         row("C1", "classification", "CPU", .2, .3, .5, 1)])
        self.assertIn("head_restriction", value["exclusion_reasons"])
        self.assertEqual(value["fifo_violation_witness"]["queued_earlier_request"], "C0")

    def test_unsupported_recorded_overlap_is_source_error_not_schedule_exclusion(self):
        with self.assertRaises(SourceIntegrityError):
            certificate_from_ledger([row("C0", "classification", "CPU", 0, 0, 1),
                                     row("C1", "classification", "GPU", .1, .2, .5, 1)])

    def test_changed_artifact_is_rejected_before_decompression(self):
        with mock.patch.object(certificate, "expected_artifact_hashes", return_value={"source_intent_mean": "pinned"}), \
             mock.patch.object(certificate, "sha", return_value="changed"), \
             mock.patch.object(certificate.Path, "read_text", return_value="{}"):
            with self.assertRaisesRegex(SourceIntegrityError, "pinned original artifact changed"):
                certificate.run("unused_mock_source")


if __name__ == "__main__":
    unittest.main()
