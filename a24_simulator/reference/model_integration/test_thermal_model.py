"""Synthetic invariants only. SOURCE ONLY; NOT RUN during preparation."""
import copy
import math
import unittest

import numpy as np

import thermal_model as thermal
import old_data


CFG = dict(cooling_tau_s=180., activity_tau_s=30., ridge=.1,
           pre_slope_tau_s=30., maximum_iterations=20000, tolerance=1e-9)


def session(sid="s1", cohort="cohort1", source="old", domain="synthetic"):
    return dict(device="A24", session_id=sid, cohort_id=cohort,
                source_family=source, source_generation="synthetic_fixture", protocol="fixture",
                observations=[dict(t_s=-10., ap_c=40., hi_s=-9.9, channel="AP", initial_eligible=True),
                              dict(t_s=0., ap_c=40., hi_s=0., channel="AP", initial_eligible=True)],
                initial_ap_c=40., initial_ap_time_s=0., initial_ap_hi_s=0., forecast_origin_s=0.,
                activity_coverage_s=[-20., 300.], owner_intervals=[],
                compatibility=dict(ap_activity_domain=domain, activity_pool_qualified=True),
                target_eligibility=dict(ap_fit=True), provenance={})


def manual_model(coefficients, support=thermal.STATES):
    return dict(status="EXPERIMENTAL_FIT", model_sha256="fixture", config=CFG,
                domains=["synthetic"], coefficients=list(coefficients),
                domain_activity_support={"synthetic": list(support)},
                domain_sources={"synthetic": ["old"]}, domain_session_counts={"synthetic": 2})


class ThermalSyntheticTests(unittest.TestCase):
    def test_declared_raw_member_false_flag_is_updated_without_duplicate_kwargs(self):
        ledger = [dict(inventory_path="synthetic_inventory", raw_root_alias="unresolved",
                       members=[dict(member_path="session/thermal.jsonl", declared_sha256="f" * 64,
                                     local_raw_bytes_reverified=False)])]
        resolved = old_data._resolve_members(ledger, {})
        self.assertEqual(len(resolved), 1)
        self.assertFalse(resolved[0]["local_raw_bytes_reverified"])
        self.assertIsNone(resolved[0]["actual_sha256"])
        self.assertEqual(resolved[0]["member_path"], "session/thermal.jsonl")

    def test_exact_idle_cooling_and_known_ambient(self):
        s = session()
        model = manual_model([25., 0., 0., 0., 0., 0., 0.])
        t = [0., 30., 180., 300.]
        p = thermal.predict(model, s, t)
        self.assertEqual(p["status"], "CONDITIONAL_AP_PREDICTION")
        np.testing.assert_allclose(p["ap_c"], [25. + 15. * math.exp(-v / 180.) for v in t], atol=1e-12)
        s["ambient_c"] = 25.
        p = thermal.predict(model, s, t)
        np.testing.assert_allclose(p["ap_c"], [25. + 15. * math.exp(-v / 180.) for v in t], atol=1e-12)

    def test_overlap_memory_and_unmeasured_schedule(self):
        s = session()
        s["owner_intervals"] = [dict(request_id="gpu", task="C", route="GPU", start_s=0., end_s=10.),
                                dict(request_id="cpu", task="D", route="CPU", start_s=5., end_s=15.)]
        segments = thermal.activity_segments(s)
        self.assertIn("classification_GPU+detection_CPU", [r["state"] for r in segments])
        model = manual_model([40., 0., 0., 1., 3., 2., 7.])
        # A 5-second GPU solo, 5-second pair, 5-second detection solo has exact
        # contributions at t=15; this hand integral does not call feature code.
        expected = (40. + 2. * (math.exp(-10. / 30.) - math.exp(-15. / 30.)) +
                    7. * (math.exp(-5. / 30.) - math.exp(-10. / 30.)) +
                    3. * (1. - math.exp(-5. / 30.)))
        p = thermal.predict(model, s, [15.])
        self.assertAlmostEqual(p["ap_c"][0], expected, places=11)
        moved = copy.deepcopy(s)
        moved["counterfactual"] = True
        moved["owner_intervals"][0].update(start_s=30., end_s=40.)
        moved["owner_intervals"][1].update(start_s=40., end_s=50.)
        q = thermal.predict(model, moved, [15.])
        self.assertNotEqual(p["ap_c"], q["ap_c"])
        self.assertTrue(q["counterfactual_schedule"])
        pre = session()
        pre["owner_intervals"] = [dict(request_id="past", task="C", route="GPU", start_s=-20., end_s=-10.)]
        f = thermal.features(pre, [0., 30.], CFG)
        self.assertGreater(f["real_activity_state_at_anchor"][2], 0.)
        self.assertLess(f["matrix"][1, 5], 0.)  # recorded prior activity cools after the anchor

    def test_unknown_AP_and_future_labels_cannot_leak(self):
        model = manual_model([25., 0., 0., 0., 0., 0., 0.])
        s = session()
        s["observations"].append(dict(t_s=100., ap_c=999., hi_s=100., channel="AP", initial_eligible=True))
        before = thermal.predict(model, s, [30., 100.])
        s["observations"][-1]["ap_c"] = -999.
        after = thermal.predict(model, s, [30., 100.])
        self.assertEqual(before["ap_c"], after["ap_c"])
        s["initial_ap_c"] = None
        self.assertEqual(thermal.predict(model, s, [30.])["status"], "UNKNOWN")
        s["initial_ap_c"] = 40.
        s["initial_ap_time_s"] = 10.
        s["initial_ap_hi_s"] = 10.
        self.assertEqual(thermal.predict(model, s, [30.])["status"], "UNKNOWN")

    def test_ridge_nonnegative_activity_and_fit_callback(self):
        sessions = []
        for index in range(3):
            s = session("fit" + str(index), "fit_cohort" + str(index))
            s["owner_intervals"] = [dict(request_id="cpu", task="C", route="CPU", start_s=10., end_s=40.)]
            s["observations"] += [dict(t_s=t, ap_c=25. + 15. * math.exp(-t / 180.), channel="AP") for t in (5., 10., 30., 60., 180.)]
            sessions.append(s)
        calls = []
        model = thermal.fit(sessions, CFG, on_fit=calls.append)
        self.assertEqual(len(calls), 1)
        self.assertEqual(model["status"], "EXPERIMENTAL_FIT")
        self.assertTrue(all(c >= 0. for c in model["coefficients"][3:7]))
        self.assertFalse(model["electrical_inputs_used"])
        self.assertIsNone(model["measured_energy_j"])

    def test_whole_cohort_and_exact_raw_session_grouping(self):
        a, b, c, d = (session("a", "A"), session("b", "A"),
                      session("c", "C", source="m8"), session("d", "D"))
        b["provenance"]["raw_session_sha256"] = "same_raw"
        c["provenance"]["raw_session_sha256"] = "same_raw"
        # Archive/container SHA equality alone must not join distinct sessions.
        a["provenance"]["source_sha256"] = d["provenance"]["source_sha256"] = "one_bundle"
        folds = thermal.grouped_folds([a, b, c, d])
        self.assertEqual(len(folds["groups"]), 2)
        for fold in folds["folds"]:
            held = set(fold["heldout_session_ids"])
            self.assertTrue({"a", "b", "c"}.issubset(held) or not {"a", "b", "c"} & held)
        unavailable = thermal.grouped_folds([a, b])
        self.assertFalse(unavailable["folds"])

    def test_supported_resource_limit_and_unmeasured_overlap_flag(self):
        s = session()
        s["owner_intervals"] = [dict(request_id="gpu", task="C", route="GPU", start_s=10., end_s=20.),
                                dict(request_id="cpu", task="D", route="CPU", start_s=10., end_s=20.)]
        model = manual_model([40., 0., 0., 1., 3., 2., 0.], support=thermal.STATES[:3])
        p = thermal.predict(model, s, [20.])
        self.assertIn("UNMEASURED_OVERLAP_ADDITIVE_SOLO_GAIN_ASSUMPTION", p["extrapolation_flags"])
        self.assertGreater(p["ap_c"][0], 40.)
        s["owner_intervals"][0]["route"] = "NPU"
        self.assertEqual(thermal.predict(model, s, [20.])["status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
