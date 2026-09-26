"""Boundary checks for the isolated fixed-episode model; no device needed."""
import unittest

from tools.d1_energy_operational_sim import at_time, predict


def fixture():
    durations = (2, 3, 2, 2, 5)
    powers = (1, 2, 3, 4, 1)
    increments = (0.5, 0, 1, -0.5, -1)
    names = ("temperature_preparation", "resident_baseline", "load",
             "post_work_wait", "resident_cooling")
    phases = {name: dict(duration_s=duration, whole_device_power_w=power,
                         ap_knots=[[0, 0], [1, increment]])
              for name, duration, power, increment in zip(names, durations, powers, increments)}
    return dict(version="energy-operational-ccdg-pc-v1", pair="CC_DG", sensor="AP",
                battery_temperature_model=None, fingerprint="a24", model_sha256={"a": "b"},
                input_sha256={"x": "y"}, cpu_threads=1,
                work_counts={"classification_CPU": 678,
                "detection_GPU": 192}, fixed_common_window_s=4,
                conditions={"serial": dict(phases=phases,
                                           transition_s={name: 0 for name in names[1:]},
                                           work_completion_s=2,
                                           observed_initial_ap_c=30)})


def run(profile=None, **overrides):
    profile = profile or fixture()
    args = dict(mode="serial", initial_ap_c=30, fingerprint="a24",
                model_sha256={"a": "b"}, input_sha256={"x": "y"},
                initial_ap_source="observed_same_episode_preload",
                work_counts={"classification_CPU": 678, "detection_GPU": 192})
    args.update(overrides)
    return predict(profile, **args)


class FixedEpisodeTests(unittest.TestCase):
    def test_phase_energy_without_duplicate_preparation_or_wait(self):
        outcome = run()
        phases = outcome["phase_trace"]
        self.assertEqual([(p["start_s"], p["end_s"]) for p in phases],
                         [(0, 2), (2, 5), (5, 7), (7, 9), (9, 14)])
        self.assertEqual(outcome["work_energy_j_conditional"], 6)
        self.assertEqual(outcome["common_window_energy_j_conditional"], 14)
        self.assertEqual(outcome["known_phase_energy_j_conditional"], 27)
        self.assertIsNone(outcome["preparation_to_cooling_energy_j_conditional"])

    def test_ap_continuity_and_residual_cooling(self):
        outcome = run()
        phases = outcome["phase_trace"]
        for previous, following in zip(phases, phases[1:]):
            self.assertEqual(previous["ap_end_c"], following["ap_start_c"])
            self.assertEqual(at_time(outcome, previous["end_s"]), previous["ap_end_c"])
        self.assertEqual(outcome["ap_end_c"], 30)
        self.assertEqual(outcome["load_ap_peak_c"], 31.5)
        self.assertIsNone(outcome["battery_temperature_prediction"])

    def test_support_boundary_and_no_arbitrary_parallel_power_sum(self):
        with self.assertRaisesRegex(ValueError, "OUT_OF_SUPPORT"):
            run(work_counts={"classification_CPU": 679, "detection_GPU": 192})
        with self.assertRaisesRegex(ValueError, "OUT_OF_SUPPORT"):
            run(sensor="BAT")
        with self.assertRaisesRegex(ValueError, "OUT_OF_SUPPORT"):
            run(cpu_threads=2)
        with self.assertRaisesRegex(ValueError, "OUT_OF_SUPPORT"):
            run(mode="parallel")
        with self.assertRaisesRegex(ValueError, "OUT_OF_SUPPORT"):
            run(initial_ap_source="synthetic")
        profile = fixture()
        profile["battery_temperature_model"] = {"copied_from_ap": True}
        with self.assertRaisesRegex(ValueError, "profile/sensor mismatch"):
            run(profile)

    def test_invalid_phase_and_missing_power_cannot_become_zero(self):
        profile = fixture()
        profile["conditions"]["serial"]["phases"]["load"]["whole_device_power_w"] = -1
        with self.assertRaisesRegex(ValueError, "invalid state"):
            run(profile)
        profile = fixture()
        profile["conditions"]["serial"]["phases"]["load"]["duration_s"] = 5
        with self.assertRaisesRegex(ValueError, "unfinished common work"):
            run(profile)

    def test_unmetered_transition_is_not_free_energy(self):
        profile = fixture()
        profile["conditions"]["serial"]["transition_s"]["load"] = 1.5
        outcome = run(profile)
        self.assertEqual(outcome["unmeasured_transition_s"], 1.5)
        self.assertIsNone(outcome["unmeasured_transition_energy_j_conditional"])
        self.assertIsNone(outcome["preparation_to_cooling_energy_j_conditional"])
        self.assertIsNone(at_time(outcome, 5.75))

    def test_partial_cooling_coverage_is_not_extrapolated_to_full_energy(self):
        profile = fixture()
        profile["conditions"]["serial"]["phases"]["resident_cooling"]["whole_device_power_w"] = None
        outcome = run(profile)
        self.assertIsNone(outcome["phase_trace"][-1]["whole_device_energy_j_conditional"])
        self.assertEqual(outcome["known_phase_energy_j_conditional"], 22)
        self.assertIsNone(outcome["preparation_to_cooling_energy_j_conditional"])


if __name__ == "__main__":
    unittest.main()
