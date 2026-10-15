"""Pure synthetic cases. No device, model, old experiment, or runtime is invoked."""
import copy
import json
import unittest
from pathlib import Path

from d1_a24_revision02_design import (NS, REVISION, first_reference,
    matches_fixed_reference, require_same_revision, validate_contract)

CONTRACT = Path(__file__).resolve().parents[1] / "docs/team/a24-measurement-revision02-20261015/CONTRACT_DRAFT.json"


def samples(value=26.9, end=60, step=2):
    return [{"before_ns": round(t * NS), "after_ns": round((t + .1) * NS), "AP_c": value}
            for t in range(0, end + 1, step)]


class RevisedInitialStateCases(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.rules = self.contract["initial_state"]["rules"]

    def test_cold_stable_reference_does_not_require_old_absolute_target(self):
        reference = first_reference(samples(), 0, self.rules)
        self.assertEqual(reference["Tref_c"], 26.9)
        self.assertGreater(abs(26.9 - 28.5), self.rules["tolerance_c"])
        self.assertFalse(reference["independent_sensor_updates_verified"])

    def test_later_arm_cannot_reanchor_itself(self):
        reference = first_reference(samples(), 0, self.rules)
        self.assertTrue(matches_fixed_reference(samples(27.1), 0, reference, self.rules))
        self.assertFalse(matches_fixed_reference(samples(28.5), 0, reference, self.rules))
        self.assertFalse(matches_fixed_reference(samples(26.0), 0, reference, self.rules))

    def test_first_eligible_window_is_kept_despite_later_values(self):
        prefix = samples()
        future = [{"before_ns": t * NS, "after_ns": t * NS + 1, "AP_c": 28.5}
                  for t in range(62, 124, 2)]
        self.assertEqual(first_reference(prefix, 0, self.rules), first_reference(prefix + future, 0, self.rules))

    def test_drift_is_not_accepted_as_a_stable_start(self):
        rows = samples()
        for row in rows:
            row["AP_c"] += .2 * row["before_ns"] / (60 * NS)
        self.assertIsNone(first_reference(rows, 0, self.rules))

    def test_missing_coverage_and_large_gap_fail_closed(self):
        self.assertIsNone(first_reference(samples(end=58), 0, self.rules))
        self.assertIsNone(first_reference([s for s in samples() if not 20 < s["before_ns"] / NS < 40], 0, self.rules))

    def test_jitter_still_has_a_bracketing_minute(self):
        rows = [{"before_ns": round(t * 2.3 * NS), "after_ns": round((t * 2.3 + .1) * NS), "AP_c": 26.9}
                for t in range(29)]
        reference = first_reference(rows, 0, self.rules)
        self.assertIsNotNone(reference)
        self.assertGreaterEqual(reference["read_before_ns"] - reference["history_start_ns"], 60 * NS)

    def test_only_post_ready_history_is_used(self):
        self.assertIsNone(first_reference(samples(), 10 * NS, self.rules))

    def test_reordered_clocks_and_nonfinite_readings_are_not_accepted(self):
        with self.assertRaises(ValueError):
            first_reference(list(reversed(samples())), 0, self.rules)
        rows = samples()
        rows[-1]["AP_c"] = float("nan")
        self.assertIsNone(first_reference(rows, 0, self.rules))

    def test_no_wait_past_frozen_bound(self):
        rows = samples()
        for row in rows:
            row["before_ns"] += 601 * NS
            row["after_ns"] += 601 * NS
        self.assertIsNone(first_reference(rows, 0, self.rules))

    def test_design_is_valid_but_never_authorizes_measurement(self):
        validate_contract(self.contract)
        modified = copy.deepcopy(self.contract)
        modified["execution_authorized"] = True
        with self.assertRaises(ValueError):
            validate_contract(modified)

    def test_budget_and_registration_are_not_reset(self):
        for change in [{"authorized_new_measurement_sessions": 32},
                       {"automatic_transfer_of_old_budget": True}, {"old_attempts_preserved": 0}]:
            modified = copy.deepcopy(self.contract)
            modified["budget"].update(change)
            with self.assertRaises(ValueError):
                validate_contract(modified)
        modified = copy.deepcopy(self.contract)
        modified["materialized_session_ids"] = ["do-not-register"]
        with self.assertRaises(ValueError):
            validate_contract(modified)

    def test_old_results_cannot_be_added_as_new_repetitions(self):
        require_same_revision([REVISION, REVISION])
        with self.assertRaises(ValueError):
            require_same_revision([REVISION, "A24-LAPTOP-PC-PREP-20261014-03"])

    def test_old_policy_ids_and_relaxed_matching_are_rejected(self):
        changed = copy.deepcopy(self.contract)
        changed["arms"][0]["policy_id"] = "BASE"
        with self.assertRaises(ValueError):
            validate_contract(changed)

    def test_unbalanced_position_or_preceding_arm_is_rejected(self):
        changed = copy.deepcopy(self.contract)
        changed["order_and_data"]["M128_proposed_orders"] = [["BASE", "ORDER", "PAIR_G", "WAIT200"]] * 4
        with self.assertRaises(ValueError):
            validate_contract(changed)
        changed = copy.deepcopy(self.contract)
        changed["initial_state"]["rules"]["tolerance_c"] = 5.0
        with self.assertRaises(ValueError):
            validate_contract(changed)


if __name__ == "__main__":
    unittest.main()
