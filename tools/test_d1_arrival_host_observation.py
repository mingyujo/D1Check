import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import d1_arrival_host_observation as h


class ObservationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.clock = 0.0
        self.calls = []
        self.device = SimpleNamespace(deadline=125.0, call=self.call)
        self.mode = 'blocked'

    def sleep(self, seconds):
        self.clock += seconds

    def call(self, *args, timeout, check):
        self.calls.append((args, timeout, self.device.deadline))
        self.assertLessEqual(timeout, 2)
        self.assertLess(self.clock, self.device.deadline)
        if 'test' in args:
            if self.mode == 'connection':
                raise OSError('connection lost')
            return SimpleNamespace(returncode=0 if self.mode == 'complete' else 1, stdout=b'', stderr=b'')
        if self.mode == 'slow':
            self.clock += min(timeout, self.device.deadline-self.clock)
            raise TimeoutError('blocked capture, not app failure')
        if '/proc/42/stack' in args:
            return SimpleNamespace(returncode=1, stdout=b'', stderr=b'Permission denied')
        return SimpleNamespace(returncode=0, stdout=b'partial journal or OS state', stderr=b'')

    def wait(self):
        with patch.object(h.time,'monotonic',side_effect=lambda:self.clock),patch.object(h.time,'sleep',side_effect=self.sleep):
            h.wait_for_cleanup(self.device,'remote',self.root/'observations','42')

    def test_blocked_app_or_journal_has_independent_three_snapshots_no_timeout_extension(self):
        with self.assertRaises(TimeoutError):self.wait()
        self.assertEqual(self.clock,125)
        report=json.loads((self.root/'observations/poll.json').read_text())
        self.assertEqual([x['offset'] for x in report['snapshots']],[5,35,105])
        self.assertEqual(self.device.deadline,125)
        self.assertTrue((self.root/'observations/at_35/power.txt').exists())
        capture=json.loads((self.root/'observations/at_35/capture.json').read_text())
        self.assertEqual(capture['commands'][-1]['status'],'unavailable')
        self.assertNotIn('kill',' '.join(' '.join(x[0]) for x in self.calls))

    def test_slow_or_failed_evidence_is_bounded_and_does_not_reset_poll(self):
        self.mode='slow'
        with self.assertRaises(TimeoutError):self.wait()
        self.assertEqual(self.clock,125)
        capture=json.loads((self.root/'observations/at_5/capture.json').read_text())
        self.assertEqual(capture['host_end']-capture['host_start'],8)
        self.assertEqual(capture['commands'][-1]['status'],'skipped_budget')

    def test_early_completion_never_waits_for_observation_schedule(self):
        self.mode='complete';self.wait()
        self.assertEqual(self.clock,0)
        self.assertEqual(len(self.calls),1)

    def test_connection_loss_preserves_host_error_without_inventing_app_failure(self):
        self.mode='connection'
        with self.assertRaises(OSError):self.wait()
        report=json.loads((self.root/'observations/poll.json').read_text())
        self.assertEqual(report['status'],'poll_failed_app_outcome_unknown')
        self.assertEqual(self.device.deadline,125)

    def test_outer_deadline_not_restarted_and_no_capture_after_end(self):
        self.device.deadline=6
        self.mode='slow'
        with self.assertRaises(TimeoutError):self.wait()
        self.assertEqual(self.clock,6)
        self.assertTrue(all(x[2] <= 6 for x in self.calls))

    def test_snapshot_disk_failure_propagates_for_runner_cleanup(self):
        with patch.object(Path,'write_bytes',side_effect=OSError('disk full')),patch.object(h.time,'monotonic',return_value=0):
            # Individual file failure remains capture failure; report write failure is fatal.
            with patch.object(h.legacy,'write_new',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):h.snapshot(self.device,'remote',self.root/'s','42',0,5)
        self.assertEqual(self.device.deadline,125)


if __name__=='__main__':unittest.main()
