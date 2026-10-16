import unittest
from tools import d1_atc_repair_policy as a
from tools import d1_atc_repair_mobile as old
from tools import d1_service_equal_mobile as ready
from tools import d1_service_equal_study as study
from tools import d1_service_equal_budget as budget


def ticket(i, task, at=35e9):
    return dict(id=str(i), ordinal=i, task=task, priority="urgent" if task == "classification" else "normal",
                arrival_ns=at, deadline_offset_ns=1.5e9 if task == "classification" else 6e9, work_units=1)


def lanes():
    return {b: dict(request=None, phase="AVAILABLE", since=35e9, dispatch=None) for b in ("CPU", "GPU")}


class Service(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f, init, _ = a.hybrid.load()
        cls.initial = init["initial"]

    def test_ready_skips_blocked_head_without_illegal_combination(self):
        c = ready.Controller(self.f, self.initial)
        ls = lanes()
        ls["CPU"].update(request=ticket(9, "detection"), phase="EXECUTING", dispatch=35e9, since=35e9)
        q = [ticket(0, "detection"), ticket(1, "classification")]
        out = c({}, q, ls, 35.1e9, {}, None, None)
        self.assertEqual(out["selected"], dict(request_id="1", backend="GPU"))
        self.assertTrue(a.legal(out["selected"], q, ls))

    def test_ready_eft_differs_from_busy_eta_eft(self):
        q = ticket(0, "classification")
        ls = lanes()
        ls["CPU"].update(request=ticket(9, "detection"), phase="EXECUTING", dispatch=35e9, since=35e9)
        c = ready.Controller(self.f, self.initial)
        c.estimates["detection_CPU_normal"] = [0., .6e9, 0., 0., 0.]
        c.estimates["classification_CPU_urgent"] = [0., .18e9, 0., 0., 0.]
        c.estimates["classification_GPU_urgent"] = [0., .35e9, 0., 0., 0.]
        original = old.eft(q, [q], ls, 35.5e9, c.estimates)
        self.assertEqual(original["job"]["backend"], "CPU")
        self.assertFalse(original["available"])
        self.assertEqual(c({}, [q], ls, 35.5e9, {}, None, None)["selected"]["backend"], "GPU")

    def test_response_does_not_free_owner(self):
        c = ready.Controller(self.f, self.initial)
        ls = lanes()
        ls["CPU"].update(request=ticket(9, "detection"), phase="PERSISTED", dispatch=35e9, since=35.6e9)
        out = c({}, [ticket(0, "detection")], ls, 35.61e9, {}, None, None)
        self.assertIsNone(out["selected"])
        self.assertEqual(out["action_kind"], "resource_wait")

    def test_arrival_cancels_hold_and_duplicate_revision(self):
        c = ready.Controller(self.f, self.initial)
        c.hold = dict(signature=(), until=37e9)
        q = ticket(0, "classification")
        c.on_public_event(dict(at_ns=35e9, event_seq=1, request_id="0", backend=None, event="arrived", ticket=q))
        self.assertIsNone(c.hold)
        c({}, [q], lanes(), 35e9, {}, None, None)
        self.assertEqual(c({}, [q], lanes(), 35e9, {}, None, None)["reason"], "duplicate_decision_revision")

    def test_frozen_workload_shard_and_no_relaxed_deadlines(self):
        cases = study.cases()
        self.assertEqual(len(cases), 64)
        self.assertEqual(len({(q["arrival_seed"], q["family"], q["level"]) for q in cases}), 64)
        self.assertEqual(4*budget.CAPS["environments"], 600)
        self.assertEqual(budget.CAPS["learning"], 0)
        for case in cases:
            self.assertEqual(len(case["requests"]) % 2, 0)
            self.assertLess(max(q["arrival_ns"] for q in case["requests"]), 119e9)
            for q in case["requests"]:
                self.assertEqual(q["work_units"], 1)
                self.assertEqual(q["deadline_offset_ns"], 1.5e9 if q["priority"] == "urgent" else 6e9)


if __name__ == "__main__":
    unittest.main()
