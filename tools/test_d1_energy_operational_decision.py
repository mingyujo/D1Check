"""Only fixed-episode decision semantics; test thresholds are illustrative."""
import unittest
from pathlib import Path

from tools.d1_energy_operational_decision import decide, query_from_recorded_profile
from tools.d1_energy_operational_sim import digest, read


ROOT = Path(__file__).resolve().parents[1] / "docs/results/energy_operational_sim_01"
PROFILE = ROOT / "frozen_profile.json"
EVALUATION = ROOT / "confirmation_evaluation.json"


def query():
    out = query_from_recorded_profile(read(PROFILE), 29.1)
    out["profile_sha256"] = digest(PROFILE)
    return out


class BoundedDecisionTests(unittest.TestCase):
    def test_no_service_limits_exposes_tradeoff_and_energy_rank_reversal(self):
        result = decide(PROFILE, EVALUATION, query())
        self.assertEqual(result["status"], "TRADEOFF")
        self.assertIsNone(result["model_candidate"])
        values = result["nominal_and_sensitivity"]
        self.assertLess(values["parallel"]["nominal"]["common_window_energy_j_conditional"],
                        values["serial"]["nominal"]["common_window_energy_j_conditional"])
        self.assertGreater(values["parallel"]["one_confirmation_error_scenario"][
            "common_window_energy_j_conditional"],
            values["serial"]["one_confirmation_error_scenario"][
                "common_window_energy_j_conditional"])
        self.assertFalse(result["policy_or_device_validation"])
        self.assertFalse(result["candidate_is_deployable"])
        self.assertEqual(result["initial_ap_evidence"]["source"],
                         "posthoc_observed_confirmation_two_arms")
        self.assertEqual(result["initial_ap_evidence"]["development_starts_c"],
                         {"serial": 29.4, "parallel": 29.2})
        self.assertIn("unvalidated", result["initial_ap_evidence"]["temperature_template"])

    def test_only_parallel_or_serial_feasible_under_hypothetical_caps(self):
        fast = query()
        fast["max_work_completion_s"] = 250.0
        fast["max_load_ap_peak_c"] = 35.0
        result = decide(PROFILE, EVALUATION, fast)
        self.assertEqual((result["status"], result["model_candidate"]),
                         ("RETROSPECTIVE_MODEL_CANDIDATE", "parallel"))
        self.assertFalse(result["candidate_is_deployable"])
        cool = query()
        cool["max_work_completion_s"] = 400.0
        cool["max_load_ap_peak_c"] = 32.0
        result = decide(PROFILE, EVALUATION, cool)
        self.assertEqual((result["status"], result["model_candidate"]),
                         ("RETROSPECTIVE_MODEL_CANDIDATE", "serial"))

    def test_threshold_crossing_and_no_feasible_arm_are_not_success(self):
        crossing = query()
        crossing["max_work_completion_s"] = 327.0
        crossing["max_load_ap_peak_c"] = 35.0
        self.assertEqual(decide(PROFILE, EVALUATION, crossing)["status"],
                         "INDETERMINATE")
        impossible = query()
        impossible["max_work_completion_s"] = 100.0
        self.assertEqual(decide(PROFILE, EVALUATION, impossible)["status"],
                         "INDETERMINATE")

    def test_support_and_metric_boundary_are_explicit(self):
        self.assertEqual(decide(PROFILE, EVALUATION, None)["status"],
                         "OUT_OF_SUPPORT")
        for field, changed in (("pair", "CG_DC"), ("resident_runtimes", 3),
                               ("cpu_threads", 2), ("sensor", "BAT"),
                               ("energy_metric", "energy_until_own_completion_j"),
                               ("work_counts", {"classification_CPU": 1}),
                               ("initial_ap_c", 29.2), ("initial_ap_c", 40.0)):
            item = query()
            item[field] = changed
            self.assertEqual(decide(PROFILE, EVALUATION, item)["status"],
                             "OUT_OF_SUPPORT", field)
        warm = query()
        warm["initial_ap_c"] = 29.2
        self.assertIn("not a physical temperature support range",
                      decide(PROFILE, EVALUATION, warm)["reason"])
        item = query()
        item["max_battery_temperature_c"] = 34
        self.assertEqual(decide(PROFILE, EVALUATION, item)["status"],
                         "OUT_OF_SUPPORT")


if __name__ == "__main__":
    unittest.main()
