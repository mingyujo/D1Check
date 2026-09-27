import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import d1_arrival_plan as p
from tools import d1_energy_ap_deploy_recovery as d


class DeploymentRecoveryTest(unittest.TestCase):
    def test_unapproved_run_cannot_claim_or_reach_device(self):
        with patch.object(d, 'check') as check, patch.object(d.recovery, 'recover') as recover:
            with self.assertRaises(ValueError):
                d.run('missing', 'adb', 'serial', False, 'hash')
            check.assert_not_called()
            recover.assert_not_called()

    def test_one_shot_claim_and_separate_deployment_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / 'plan.json'
            d.write_new(plan, dict(registry=str(root / 'registry'), output_root=str(root / 'output')))
            with patch.object(d, 'check', return_value={'status': 'PC_READY_DEVICE_UNVERIFIED_NOT_APPROVED'}), \
                 patch.object(d.recovery, 'recover', return_value={'status': 'verified'}) as recover:
                result = d.run(plan, 'adb', 'serial', True, p.digest(plan))
                self.assertEqual(result['status'], 'verified')
                self.assertTrue((root / 'registry/claim.json').exists())
                self.assertTrue((root / 'registry/complete.json').exists())
                recover.assert_called_once()
                self.assertTrue(recover.call_args.kwargs['root_only'])
                self.assertTrue(recover.call_args.kwargs['require_hardware_serial'])
                with self.assertRaises(FileExistsError):
                    d.run(plan, 'adb', 'serial', True, p.digest(plan))
                self.assertEqual(recover.call_count, 1)

    def test_failure_is_stopped_and_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / 'plan.json'
            d.write_new(plan, dict(registry=str(root / 'registry'), output_root=str(root / 'output')))
            with patch.object(d, 'check'), patch.object(d.recovery, 'recover', side_effect=RuntimeError('push timeout')) as recover:
                with self.assertRaises(RuntimeError):
                    d.run(plan, 'adb', 'serial', True, p.digest(plan))
                self.assertEqual(json.loads((root / 'registry/stopped.json').read_text())['status'],
                                 'stopped_no_resume')
                with self.assertRaises(FileExistsError):
                    d.run(plan, 'adb', 'serial', True, p.digest(plan))
                self.assertEqual(recover.call_count, 1)

    def test_prepared_bundle_check_is_pc_only(self):
        file = os.environ.get('D1_ENERGY_DEPLOY_PLAN')
        if not file:
            self.skipTest('prepared bundle not supplied')
        from tools import d1_arrival_device as device
        with patch.object(device, 'Device', side_effect=AssertionError('device reached')) as adb:
            result = d.check(file)
            adb.assert_not_called()
        self.assertEqual(result['device_calls'], 0)
        self.assertEqual(result['collection_sessions'], 0)
        self.assertEqual(result['recovery_seconds'], 600)

    def test_reused_client_records_without_owning_shared_daemon(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(d.recovery.rp, 'run', return_value={'status': 'returned', 'returncode': 0}) as command:
            device = d.recovery.device_class(root_only=True)('adb', 'selected', Path(tmp))
            device.deadline = time.monotonic() + 30
            device.call('version', timeout=2)
            self.assertTrue(command.call_args.kwargs['root_only'])


if __name__ == '__main__':
    unittest.main()
