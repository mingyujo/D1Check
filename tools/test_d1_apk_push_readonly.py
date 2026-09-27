import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import d1_apk_push_readonly as d


class ReadOnlyPushTest(unittest.TestCase):
    def test_stat_and_transport_parser(self):
        self.assertEqual(d.parse_stat(b'106092116:1790000000\n'),
                         dict(bytes=106092116,mtime_epoch_seconds=1790000000))
        with self.assertRaises(ValueError):d.parse_stat(b'')
        serial='adb-example._adb-tls-connect._tcp'
        self.assertEqual(d.parse_devices(('List of devices attached\n'+serial+' device\n').encode()),serial)
        with self.assertRaises(ValueError):d.parse_devices(b'List of devices attached\n')

    def test_prepared_check_cannot_reach_device(self):
        file=os.environ.get('D1_APK_PUSH_READONLY_PLAN')
        if not file:self.skipTest('prepared plan not supplied')
        with patch.object(d.rp,'run',side_effect=AssertionError('ADB reached')) as command:
            if Path(json.loads(Path(file).read_text(encoding='utf-8'))['output_root']).exists():
                with self.assertRaisesRegex(ValueError, 'diagnosis already consumed'):
                    d.check(file)
            else:
                result=d.check(file)
                self.assertEqual((result['adb_commands_max'],result['total_seconds']), (9,300))
            command.assert_not_called()

    def test_run_only_uses_allowlisted_readonly_commands_and_size_gates_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan=root/'plan.json';out=root/'run'
            d.write_new(plan,dict(adb='adb',output_root=str(out),apk_bytes=106092116,
                device_model='SM-A245N',device_fingerprint='fingerprint',device_hardware_serial='hardware'))
            serial='adb-approved._adb-tls-connect._tcp'
            outputs=[f'List of devices attached\n{serial} device\n'.encode(),b'SM-A245N\n',
                     b'fingerprint\n',b'hardware\n',b'100:1\n',b'106092116:2\n',
                     b'Filesystem 1K-blocks Used Available Use% Mounted on\n',
                     (d.EXPECTED_APK+'  remote\n').encode()]
            calls=[]
            def fake_run(cmd,folder,timeout,display,root_only):
                self.assertTrue(root_only)
                self.assertLessEqual(timeout,120)
                self.assertNotIn(cmd[-1],('push','pull','install'))
                calls.append(cmd)
                folder.mkdir(parents=True)
                (folder/'stdout.bin').write_bytes(outputs.pop(0))
                (folder/'stderr.bin').write_bytes(b'')
                d.write_new(folder/'result.json',dict(status='returned',returncode=0))
                return dict(status='returned',returncode=0,elapsed_seconds=0.01)
            class Socket:
                def __enter__(self):return self
                def __exit__(self,*args):return False
            with patch.object(d,'check'),patch.object(d.p,'digest',return_value='sha'), \
                 patch.object(d.socket,'create_connection',return_value=Socket()), \
                 patch.object(d.rp,'run',side_effect=fake_run):
                result=d.run(plan,'sha')
            self.assertEqual(result['status'],'completed_read_only')
            self.assertEqual(result['commands_used'],8)
            self.assertEqual(sum('sha256sum' in x for cmd in calls for x in cmd),1)
            self.assertEqual(result['remote']['old_collection']['sha256_status'],
                             'not_queried_size_not_candidate')
            self.assertEqual(result['remote']['deployment_recovery']['sha256_status'],'matches_candidate')
            self.assertEqual((result['transfer_attempts'],result['install_attempts']), (0,0))


if __name__=='__main__':unittest.main()
