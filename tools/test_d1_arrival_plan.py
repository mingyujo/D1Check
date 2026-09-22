import unittest

from tools import d1_arrival_plan as p


class ArrivalPlanTest(unittest.TestCase):
    def test_budget_and_workload_shape(self):
        self.assertEqual(len(p.recipes()), 6)
        self.assertEqual(len(p.trace("burst", "classification")), 8)
        self.assertEqual(len(p.trace("queue", "classification")), 6)
        self.assertEqual(len(p.trace("low", "classification")), 4)
        events = p.trace("burst", "classification")
        self.assertTrue(any(task == "detection" and priority == "normal" and at < 450
                            for at, task, priority in events))
        self.assertTrue(any(task == "classification" and priority == "urgent" and at == 450
                            for at, task, priority in events))

    def test_reversed_task_role_is_distinct(self):
        forward = p.trace("burst", "classification")
        reversed_role = p.trace("burst", "detection")
        self.assertEqual([x[0] for x in forward], [x[0] for x in reversed_role])
        self.assertEqual([x[2] for x in forward], [x[2] for x in reversed_role])
        self.assertNotEqual([x[1] for x in forward], [x[1] for x in reversed_role])


if __name__ == "__main__":
    unittest.main()
