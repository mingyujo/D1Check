import collections
import tempfile
import unittest
from pathlib import Path

from tools.d1_a24_laptop_plan import ARMS, M128_DELTA_NS, bank, encode, make_plan, write_plan


class PlanTests(unittest.TestCase):
    def test_recipe_exact_counts_and_deadlines(self):
        for recipe, counts in [("L64", {"C": 32, "D": 32}), ("C252", {"C": 252}), ("M128", {"C": 96, "D": 32})]:
            b = bank("fresh-PC-only", "DEV01", recipe, 11)
            self.assertEqual(dict(collections.Counter(r["task"] for r in b["requests"])), counts)
            for r in b["requests"]:
                self.assertEqual(r["deadline_ns"] - r["scheduled_arrival_ns"], 2_200_000_000 if r["task"] == "C" else 5_000_000_000)
            self.assertFalse(b["inputs_bound"])
        self.assertEqual(bank("a", "b", "C252", 1)["requests"][-1]["scheduled_arrival_ns"], 118_633_200_000)
        self.assertEqual(M128_DELTA_NS, 2_032_194_000)

    def test_plan_stages_pairing_and_no_consumption(self):
        p, banks = make_plan("fresh-PC-only")
        self.assertEqual(dict(collections.Counter(s["stage"] for s in p["sessions"])), {"I": 4, "F": 4, "DEV": 16, "CONFIRM": 40})
        self.assertEqual(len({s["session_id"] for s in p["sessions"]}), 64)
        self.assertTrue(all(s["state"] == "PLANNED_UNCONSUMED" and not s["consumed"] for s in p["sessions"]))
        self.assertEqual(len([s for s in p["sessions"] if s["stage"] == "DEV" and s["wait_ms"] == 200]), 2)
        for block in ["DEV01", "DEV02", "CONFIRM01", "CONFIRM02", "CONFIRM03", "CONFIRM04", "CONFIRM05"]:
            pair = [s for s in p["sessions"] if s["block"] == block and s["recipe"] == "M128"]
            self.assertEqual(len(pair), 4)
            self.assertEqual(len({s["bank_sha256"] for s in pair}), 1)
        dev_ids = {r["request_id"] for k,b in banks.items() if k.startswith("DEV") for r in b["requests"]}
        confirm_ids = {r["request_id"] for k,b in banks.items() if k.startswith("CONFIRM") for r in b["requests"]}
        self.assertFalse(dev_ids & confirm_ids)

    def test_repeatable_seeds_and_prescriptions(self):
        self.assertEqual(encode(make_plan("new-fresh-identity")[0]), encode(make_plan("new-fresh-identity")[0]))
        self.assertEqual({x[0] for x in ARMS}, {"L64", "C252", "M128"})
        self.assertNotEqual(make_plan("a")[0]["sessions"][0]["session_id"], make_plan("b")[0]["sessions"][0]["session_id"])

    def test_bound_single_image_does_not_invent_diversity(self):
        bindings = {"approved_inputs": [{"input_file": "approved.png", "input_sha256": "a" * 64, "tensor_sha256": {"C": "b" * 64, "D": "c" * 64}}]}
        b = bank("p", "b", "M128", 23, bindings)
        self.assertTrue(b["inputs_bound"])
        self.assertEqual(b["input_diversity"], "SINGLE_APPROVED_IMAGE_REPEATED")
        self.assertEqual(len({r["input_file"] for r in b["requests"]}), 1)

    def test_write_once_no_registry_or_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "new-plan"
            write_plan(out, "new-id")
            with self.assertRaises(FileExistsError): write_plan(out, "new-id")
            self.assertFalse((out / "registry").exists())
            self.assertFalse((out / "claim.json").exists())


if __name__ == "__main__": unittest.main()
