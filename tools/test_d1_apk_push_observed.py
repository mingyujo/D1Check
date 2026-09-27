import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import d1_apk_push_observed as d


class ObservedPushTest(unittest.TestCase):
    def test_progress_is_evidence_of_remote_size_only(self):
        self.assertEqual(d.progress_classification([]), 'progress_unobserved')
        self.assertEqual(d.progress_classification([
            {'seconds': 20, 'bytes': 10}, {'seconds': 40, 'bytes': 20}]),
            'remote_size_increased_observed')
        self.assertEqual(d.progress_classification([
            {'seconds': second, 'bytes': 10} for second in (20, 40, 60, 80)]),
            'remote_size_plateau_observed_not_proof_of_no_transfer')

    def test_storage_parser_rejects_missing_available_count(self):
        self.assertEqual(d.parse_available_bytes(
            b'Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block 100 20 80 20% /data\n'),
            80*1024)
        with self.assertRaises(ValueError):d.parse_available_bytes(b'empty\n')

    def test_check_is_pc_only_and_run_requires_separate_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apk = root/'candidate.apk'; apk.write_bytes(b'apk')
            adb = root/'adb.exe'; adb.write_bytes(b'adb')
            identity = root/'readonly-plan.json'
            identity.write_text(json.dumps(dict(experiment_id='ENERGY-AP-PUSH-READONLY-01',
                device_model='SM-A245N', device_fingerprint='fingerprint',
                device_hardware_serial='hardware')))
            prior = root/'readonly.json'
            prior.write_text(json.dumps({'status': 'completed_read_only',
                'plan_sha256': d.p.digest(identity), 'remote': {
                'old_collection': {'status': 'stat_failed', 'stderr': 'No such file or directory'},
                'deployment_recovery': {'status': 'stat_failed', 'stderr': 'No such file or directory'}}}))
            with patch.object(d, 'APK_SHA', d.p.digest(apk)), patch.object(d, 'APK_BYTES', 3), \
                 patch.object(d.rp, 'run',
                    side_effect=AssertionError('device command reached')) as device:
                prepared = d.prepare(root/'bundle', apk, adb, prior, identity)
                plan = root/'bundle'/'diagnosis_plan.json'
                self.assertEqual(prepared['status'], 'PC_READY_NOT_APPROVED_DEVICE_UNVERIFIED')
                self.assertEqual(prepared['total_adb_command_cap'], 17)
                self.assertEqual(d.check(plan)['device_calls'], 0)
                with self.assertRaisesRegex(ValueError, 'separate frozen-plan approval'):
                    d.run(plan, prepared['plan_sha256'], approved=False)
                device.assert_not_called()

    def test_plan_has_no_install_or_retry_and_a_direct_remote_path(self):
        self.assertEqual(d.REMOTE.rsplit('/', 1)[0], '/data/local/tmp')
        self.assertEqual(len(d.PROBE_SECONDS), 8)
        self.assertEqual((6 + 1 + len(d.PROBE_SECONDS) + 1 + 1), 17)

    def test_recorded_execution_checks_remote_sha_even_after_client_return(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); plan = root/'plan.json'; out = root/'output'
            serial = 'adb-approved._adb-tls-connect._tcp'
            d.write_new(plan, dict(output_root=str(out), total_seconds=420, adb='adb',
                model='SM-A245N', fingerprint='fingerprint', hardware_serial='hardware',
                apk='candidate.apk', apk_bytes=106092116, remote_apk=d.REMOTE,
                total_adb_command_cap=17))
            outputs = [f'List of devices attached\n{serial} device\n'.encode(),
                       b'SM-A245N\n', b'fingerprint\n', b'hardware\n',
                       b'', b'Filesystem 1K-blocks Used Available Use% Mounted on\n/dev/block 300000 1 200000 1% /data\n',
                       b'', b'106092116:1790000000\n',
                       (d.APK_SHA+'  '+d.REMOTE+'\n').encode()]
            calls = []
            def fake_run(cmd, folder, timeout, display, root_only):
                self.assertTrue(root_only)
                self.assertFalse(any(x in ('pull', 'install', 'pm') for x in cmd))
                calls.append(cmd)
                folder.mkdir(parents=True)
                (folder/'stdout.bin').write_bytes(outputs.pop(0))
                is_absent = 'stat' in cmd and len(calls)==5
                (folder/'stderr.bin').write_bytes(b'No such file or directory' if is_absent else b'')
                return dict(status='nonzero_exit' if is_absent else 'returned',
                            returncode=1 if is_absent else 0, elapsed_seconds=.01)
            class Socket:
                def __enter__(self):return self
                def __exit__(self,*args):return False
            with patch.object(d, 'check'), patch.object(d.p, 'digest', return_value='sha'), \
                 patch.object(d.socket, 'create_connection', return_value=Socket()), \
                 patch.object(d.rp, 'run', side_effect=fake_run):
                receipt = d.run(plan, 'sha', approved=True)
            self.assertEqual(receipt['status'], 'transfer_verified')
            self.assertEqual(receipt['adb_commands_used'], 9)
            self.assertEqual(len(calls), 9)
            self.assertEqual((receipt['push_attempts'], receipt['install_attempts']), (1, 0))


if __name__ == '__main__':
    unittest.main()
