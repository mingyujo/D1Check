import unittest
from tools import d1_simple_mobile_policy as m
from tools import d1_atc_repair_policy as a


def q(i, task="classification"):
    return dict(id=str(i), ordinal=i, task=task, priority="urgent" if task == "classification" else "normal", arrival_ns=35e9,
                deadline_offset_ns=1.5e9 if task == "classification" else 6e9, work_units=1)


def lanes():
    return {b: dict(request=None, phase="AVAILABLE", since=35e9, dispatch=None) for b in ("CPU", "GPU")}


class Simple(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f, i, _ = a.hybrid.load()
        cls.initial = i["initial"]

    def test_rr_pointer_moves_only_on_actual_dispatch(self):
        c = m.Controller(self.f, self.initial, "RR_READY")
        ticket = q(0)
        c.on_public_event(dict(event_seq=1, event="arrived", at_ns=35e9, request_id="0", backend=None, ticket=ticket))
        out = c({}, [ticket], lanes(), 35e9, {}, None, None)
        self.assertEqual(out["selected"]["backend"], "CPU")
        self.assertEqual(c.cursor, 0)
        self.assertIsNone(c({}, [ticket], lanes(), 35e9, {}, None, None)["selected"])
        self.assertEqual(c.cursor, 0)
        c.on_public_event(dict(event_seq=2, event="dispatch_ns", at_ns=35e9, request_id="0", backend="CPU"))
        self.assertEqual(c.cursor, 1)
        self.assertEqual(c({}, [q(1)], lanes(), 35e9, {}, None, None)["selected"]["backend"], "GPU")

    def test_rr_unsupported_busy_and_physical_masks(self):
        c = m.Controller(self.f, self.initial, "RR_READY")
        c.cursor = 1
        self.assertEqual(c({}, [q(0, "detection")], lanes(), 35e9, {}, None, None)["selected"]["backend"], "CPU")
        ls = lanes()
        ls["CPU"].update(request=q(9, "detection"), phase="EXECUTING", dispatch=35e9)
        c.last_key = None
        out = c({}, [q(0, "detection"), q(1)], ls, 35e9, {}, None, None)
        self.assertEqual(out["selected"], dict(request_id="1", backend="GPU"))
        self.assertTrue(a.legal(out["selected"], [q(0, "detection"), q(1)], ls))

    def test_greedy_per_resource_fifo_not_global_headblocking(self):
        c = m.Controller(self.f, self.initial, "GREEDY_RESOURCE_FIFO", {"classification": "GPU", "detection": "CPU"})
        ls = lanes()
        ls["CPU"].update(request=q(9, "detection"), phase="PERSISTED", dispatch=35e9)
        qs = [q(0, "detection"), q(1), q(2)]
        self.assertEqual(c({}, qs, ls, 35e9, {}, None, None)["selected"], dict(request_id="1", backend="GPU"))

    def test_affinity_static_measured_and_cpu_weakness(self):
        data = m.preferences()
        self.assertEqual(data["preferred"], {"classification": "CPU", "detection": "CPU"})
        self.assertEqual(data["estimates"]["classification_CPU"]["n"], 4)
        c = m.Controller(self.f, self.initial, "GREEDY_RESOURCE_FIFO")
        c.estimates["classification_CPU_urgent"] = [100e9]*5
        self.assertEqual(c({}, [q(0)], lanes(), 35e9, {}, None, None)["selected"]["backend"], "CPU")


if __name__ == "__main__":
    unittest.main()
