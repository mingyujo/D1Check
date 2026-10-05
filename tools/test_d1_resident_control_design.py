import copy
import json
import subprocess
import sys
import unittest
from tools import d1_resident_control_design as d


class DesignTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((d.BUNDLE/'design_plan.json').read_text(encoding='utf-8'))

    def test_actual_pc_entry(self):
        result = subprocess.run([sys.executable, '-B', '-m',
            'tools.d1_resident_control_design', 'check'], cwd=d.ROOT,
            capture_output=True, text=True, encoding='utf-8', timeout=20)
        drift = any(d.digest(d.ROOT/f)!=sha for f,sha in self.plan['evidence_sha256'].items())
        if drift:
            # Archived pre-implementation design remains immutable, not silently rebound.
            self.assertNotEqual(result.returncode,0)
            self.assertIn('evidence changed',result.stderr)
        else:
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload['execution_ready'])
            self.assertEqual(payload['device_commands'], 0)

    def test_no_run_action(self):
        result = subprocess.run([sys.executable, '-B', '-m',
            'tools.d1_resident_control_design', 'run'], cwd=d.ROOT,
            capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 2)

    def test_budget_and_control_cannot_be_silently_changed(self):
        mutations = [('explicit_inferences', 64), ('total_seconds', 2120),
                     ('adb_commands', 6601), ('retry', 1)]
        for key, value in mutations:
            with self.subTest(key=key):
                plan = copy.deepcopy(self.plan)
                plan['proposed_budget'][key] = value
                with self.assertRaises(AssertionError): d.check(plan)
        self.plan['sessions'][0]['work_requests'] = 24
        with self.assertRaises(AssertionError): d.check(self.plan)

    def test_blocked_design_is_not_execution_approval(self):
        self.plan['execution_ready'] = True
        with self.assertRaises(AssertionError): d.check(self.plan)

    def test_source_drift_rejected(self):
        self.plan['evidence_sha256'][next(iter(self.plan['evidence_sha256']))] = '0'*64
        with self.assertRaises(AssertionError): d.check(self.plan)


if __name__ == '__main__': unittest.main()
