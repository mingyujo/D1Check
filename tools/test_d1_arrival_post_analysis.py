import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import d1_arrival_post_analysis as post
from tools import d1_arrival_simulation_plan as sim


class ArrivalPostAnalysisTest(unittest.TestCase):
    def test_condition_labels_and_pooled_p95(self):
        self.assertEqual(post.condition(dict(kind="burst", urgent_task="classification")), "primary")
        self.assertEqual(post.condition(dict(kind="burst", urgent_task="detection")), "reversed")
        self.assertEqual(post.condition(dict(kind="queue", urgent_task="classification")), "queue")
        rows = [dict(response_ns=x, terminal_status="succeeded") for x in (1, 2, 3, 4)]
        self.assertEqual(post.pooled_p95_ms(rows), 4 / 1e6)

    def test_representative_rule_is_first_complete_primary_pair(self):
        sessions = []
        for policy in post.POLICIES:
            sessions.append(dict(condition="primary", entry=dict(replicate=0, policy=policy, pair_id="p")))
            sessions.append(dict(condition="primary", entry=dict(replicate=1, policy=policy, pair_id="q")))
        selected = post.representative_sessions(sessions)
        self.assertEqual([x["entry"]["policy"] for x in selected], list(post.POLICIES))
        self.assertEqual({x["entry"]["pair_id"] for x in selected}, {"p"})

    def test_simulation_plan_preserves_fail_and_has_no_execution(self):
        audit = dict(status="PASS", frozen_decision={"conditional_joint_primary_pass": False})
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.json"
            audit_path.write_text(json.dumps(audit), encoding="utf-8")
            plan = sim.make_plan(audit_path)
            self.assertTrue(sim.validate(plan))
            self.assertEqual(plan["status"], "PLAN_ONLY_NOT_EXECUTED")
            self.assertIn("response_ns", plan["timing_model"]["forbidden"])
            with patch("tools.d1_arrival_simulation_plan.validate", wraps=sim.validate):
                output = Path(tmp) / "out"
                receipt = sim.generate(audit_path, output)
                result = sim.dry_run(output / "simulation_plan.json", receipt["plan_sha256"])
            self.assertEqual(result["simulation_runs"], 0)
            self.assertEqual(result["simulated_completions"], 0)

    def test_simulation_plan_rejects_success_criterion_and_request_unit(self):
        audit = dict(status="PASS", frozen_decision={"conditional_joint_primary_pass": False})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.json"; path.write_text(json.dumps(audit))
            plan = sim.make_plan(path)
            for mutate in (lambda p: p["separation"].update(success_criteria="pass"),
                           lambda p: p["statistics"].update(unit="request"),
                           lambda p: p["budget"].update(random_draws=1)):
                changed = copy.deepcopy(plan); mutate(changed)
                with self.assertRaises(ValueError):
                    sim.validate(changed)


if __name__ == "__main__":
    unittest.main()
