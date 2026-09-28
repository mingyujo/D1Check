"""PC-only run entry tests for a terminal app failure and single host cleanup."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import d1_arrival_plan as plan_io
from tools import d1_energy_ap_autonomous_diag as diag
from tools import d1_energy_collection_device as runner
from tools import d1_energy_state_collection as state


class FakeDevice:
    def __init__(self, *args, **kwargs):
        self.deadline = None
        self.sequence = 0
        self.command_limit = None

    def call(self, *args, **kwargs):
        self.sequence += 1
        return subprocess.CompletedProcess(args, 0, b'', b'')


class LifecycleCleanupTest(unittest.TestCase):
    def fixture(self, base):
        manifest = base/'manifest.json'
        manifest.write_text(json.dumps(dict(session_control=diag.CONTROL,
            autonomous_diagnostic_only=True)), encoding='utf-8')
        file = base/'plan.json'
        file.write_text(json.dumps(dict(state_model_calibration=True,
            autonomous_diagnostic_only=True, diagnostic_only=True,
            protocol=state.PROTOCOL, experiment_id=diag.EXPERIMENT,
            output_root=str(base/'run'), registry=str(base/'registry'),
            budget=diag.BUDGET, apk_preflight={'candidate': {}},
            apk_sha256='fixture', source_files={}, entries=[dict(index=0,
                phase='confirmation', pair='CG_DC', mode='calibration',
                session_id='fixture', manifest=manifest.name)])), encoding='utf-8')
        return file

    @staticmethod
    def recovered(_device, _remote, folder, *_args):
        folder.mkdir(parents=True)
        (folder/'cleanup.json').write_text(json.dumps(dict(status='failed',
            error='stopped: lifecycle_cancelled/null')), encoding='utf-8')
        (folder/'session_failure.json').write_text(json.dumps(dict(
            exception_class='java.lang.IllegalStateException',
            stack='original lifecycle stack')), encoding='utf-8')
        return {'status': 'recovered'}

    def run_failure(self, base, cleanup_side_effect=None, recover_side_effect=None):
        file = self.fixture(base)
        with patch.object(diag, 'check'), \
             patch.object(runner, 'ObservedDevice', FakeDevice), \
             patch.object(runner, 'installation', return_value={'status': 'verified'}), \
             patch.object(runner, 'gates'), \
             patch.object(runner.install, 'installed_hash', return_value='fixture'), \
             patch.object(runner.shared, 'stage_inputs', return_value='remote'), \
             patch.object(runner, 'poll'), \
             patch.object(runner, 'recover', side_effect=recover_side_effect or self.recovered), \
             patch.object(runner, 'pull_file', side_effect=OSError('fixture prefix unavailable')), \
             patch.object(runner.shared, 'cleanup', side_effect=cleanup_side_effect,
                          return_value={'status': 'completed'}) as cleanup, \
             patch.object(state, 'summarize_session', side_effect=ValueError('app completion/identity')):
            with self.assertRaises(Exception):
                runner.run(file, 'FAKE_ADB_NOT_EXECUTED', None, plan_io.digest(file), True)
        receipt = json.loads((base/'run/FINAL_RECEIPT.json').read_text(encoding='utf-8'))
        return receipt, cleanup, base/'run/00_fixture'

    def test_app_failure_after_cleanup_does_not_force_stop_twice(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt, cleanup, session = self.run_failure(Path(tmp))
            self.assertEqual(cleanup.call_count, 1)
            self.assertEqual(receipt['host_cleanup']['status'], 'completed')
            self.assertEqual(receipt['app_terminal_evidence']['cleanup.json']['status'], 'failed')
            self.assertIn('original lifecycle stack',
                          receipt['app_terminal_evidence']['session_failure.json']['stack'])
            self.assertIn('app completion/identity', receipt['error'])
            self.assertTrue((session/'host_cleanup.json').exists())
            self.assertFalse((session/'failure_host_cleanup.json').exists())

    def test_partial_cleanup_failure_is_not_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt, cleanup, _ = self.run_failure(Path(tmp),
                cleanup_side_effect=RuntimeError('fixture force-stop outcome unknown'))
            self.assertEqual(cleanup.call_count, 1)
            self.assertEqual(receipt['host_cleanup']['status'],
                             'attempted_outcome_unknown_no_retry')
            self.assertIn('fixture force-stop outcome unknown', receipt['error'])
            self.assertEqual(receipt['status'], 'stopped_no_resume')

    def test_recovery_failure_still_gets_first_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt, cleanup, _ = self.run_failure(Path(tmp),
                recover_side_effect=OSError('fixture archive failed'))
            self.assertEqual(cleanup.call_count, 1)
            self.assertEqual(receipt['host_cleanup']['status'], 'completed')
            self.assertIn('fixture archive failed', receipt['error'])


if __name__ == '__main__':
    unittest.main()
