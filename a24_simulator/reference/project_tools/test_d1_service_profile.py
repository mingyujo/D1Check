from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.d1_service_profile import build, describe


class ServiceProfileTest(unittest.TestCase):
    def test_nearest_rank_and_empty(self):
        self.assertEqual(describe(list(range(1,21)))['p95_ns'],19)
        self.assertIsNone(describe([])['p95_ns'])

    def test_failure_kept_in_all_arrival_denominator(self):
        common = dict(task_id='detection', requested_backend='CPU', priority='urgent', role='calibration', cold=False)
        receipt = dict(session_id='session', source_manifest_sha256='a'*64, gpu=dict(status='not_requested'),
                       sampled_peak_pss_kb=100, max_thermal_status=0, events=[
                           dict(common, terminal_status='succeeded', service_ns=20, completion_ns=40, scheduled_arrival_ns=10, prepare_ns=2),
                           dict(common, terminal_status='failed')])
        with tempfile.TemporaryDirectory() as directory, patch('tools.d1_service_profile.validate', return_value=receipt), patch('tools.d1_service_profile.digest', return_value='b'*64), patch('tools.d1_service_profile.read', return_value=dict(purpose='solo',apk_sha256='c'*64,device_fingerprint='test')):
            result = build([Path(directory)])
            group = next(iter(result['sessions'][0]['groups'].values()))
            self.assertEqual(group['service_success_rate'], .5)
            self.assertEqual(group['response']['p95_ns'],30)
            self.assertEqual(result['status'],'diagnostic_not_frozen')
            with self.assertRaises(ValueError):
                build([directory,directory])
