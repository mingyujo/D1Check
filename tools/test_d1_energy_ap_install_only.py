import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import d1_energy_ap_install_only as d


class Response:
    def __init__(self, stdout=b'', returncode=0):
        self.stdout=stdout;self.returncode=returncode


class FakeDevice:
    latest=None
    def __init__(self, adb, root):
        self.adb=adb;self.root=root;self.deadline=None;self.sequence=0
        self.pulls=0;self.installs=0;self.last_identity={'model':'SM-A245N'}
        self.calls=[];FakeDevice.latest=self
    def call(self,*args,timeout=30,check=True):
        self.calls.append(args);self.sequence+=1
        if args[:3]==('shell','pm','install'):
            self.installs+=1;return Response(b'Success\n')
        if args[-1]=='ro.serialno':return Response(b'hardware\n')
        if args[-1]=='battery':return Response(b'level: 80\n')
        if args[-1]=='thermalservice':return Response(b'Thermal Status: 0\n')
        return Response()


class InstallOnlyTest(unittest.TestCase):
    def test_remote_sha_parser_requires_exact_path(self):
        class Device:
            def __init__(self, value):self.value=value
            def call(self,*args,**kwargs):return Response(self.value)
        good=(d.APK_SHA+'  '+d.REMOTE+'\n').encode()
        self.assertEqual(d.remote_hash(Device(good),d.REMOTE),d.APK_SHA)
        with self.assertRaises(ValueError):
            d.remote_hash(Device((d.APK_SHA+'  /wrong.apk\n').encode()),d.REMOTE)

    def test_device_wrapper_blocks_push_and_second_install(self):
        class Parent:
            def __init__(self,adb,serial,root):self.sequence=0;self.serial='selected'
            def call(self,*args,**kwargs):self.sequence+=1;return Response()
        with patch.object(d.recovery,'device_class',return_value=Parent):
            device=d.recorded_device()('adb',Path('unused'))
            with self.assertRaisesRegex(ValueError,'push forbidden'):device.call('push','apk','remote')
            device.call('shell','pm','install','-r','remote')
            with self.assertRaisesRegex(ValueError,'second install'):device.call('shell','pm','install','-r','remote')

    def test_live_transport_is_selected_before_recorded_serial_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            serial='adb-example._adb-tls-connect._tcp'
            values=[('List of devices attached\n'+serial+' device\n').encode(),
                    b'SM-A245N\n',b'fingerprint\n']
            calls=[]
            def fake_run(command,folder,timeout,display,root_only):
                calls.append(command)
                folder.mkdir(parents=True)
                (folder/'stdout.bin').write_bytes(values.pop(0))
                (folder/'stderr.bin').write_bytes(b'')
                return dict(status='returned',returncode=0)
            with patch.object(d.rp,'run',side_effect=fake_run):
                device=d.recorded_device()('adb',Path(tmp)/'commands')
                device.deadline=time.monotonic()+30
                identity=device.identify('fingerprint')
            self.assertEqual(identity['serial'],serial)
            self.assertEqual(calls[0],['adb','devices','-l'])
            self.assertEqual(calls[1][:3],['adb','-s',serial])
            self.assertEqual(len(calls),3)

    def test_one_install_and_remote_mismatch_stop(self):
        for remote_digest,expected_install in ((d.APK_SHA,1),('0'*64,0)):
            with self.subTest(remote_digest=remote_digest),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);plan=root/'plan.json'
                candidate=dict(package='example',version_code=1,signer_sha256='signer',apk_sha256=d.APK_SHA)
                q=dict(output_root=str(root/'output'),registry=str(root/'registry'/'id'),
                       adb='adb',device_hardware_serial='hardware',screen_contract={},candidate=candidate)
                plan.write_text(json.dumps(q))
                before=dict(candidate,apk_sha256='old')
                def preflight(device,plan_data,folder):
                    return dict(candidate=candidate,installed=before)
                with patch.object(d,'check'),patch.object(d.p,'digest',return_value='plan-sha'), \
                     patch.object(d,'recorded_device',return_value=FakeDevice), \
                     patch.object(d.apk,'preflight',side_effect=preflight), \
                     patch.object(d.legacy,'require_stopped'), \
                     patch.object(d.legacy,'battery_gate'), \
                     patch.object(d.shared,'screen_snapshot'), \
                     patch.object(d.shared,'cleanup',return_value=dict(status='completed')), \
                     patch.object(d.recovery,'installed_hash',return_value=d.APK_SHA), \
                     patch.object(d,'remote_hash',return_value=remote_digest):
                    if expected_install:
                        result=d.run(plan,'plan-sha',True)
                        self.assertEqual(result['status'],'verified')
                    else:
                        with self.assertRaisesRegex(ValueError,'no retry'):
                            d.run(plan,'plan-sha',True)
                        result=json.loads((root/'output'/'receipt.json').read_text())
                        self.assertEqual(result['status'],'failed')
                    self.assertEqual(result['install_attempts'],expected_install)
                    self.assertEqual(result['push_attempts'],0)
                    self.assertEqual(result['cleanup']['status'],'completed')

    def test_pc_check_does_not_reach_adb(self):
        path=os.environ.get('D1_INSTALL_ONLY_PLAN')
        if not path:self.skipTest('prepared install-only plan not supplied')
        with patch.object(d.rp,'run',side_effect=AssertionError('device reached')) as client:
            plan=json.loads(Path(path).read_text(encoding='utf-8'))
            if Path(plan['output_root']).exists():
                with self.assertRaisesRegex(ValueError,'consumed'):
                    d.check(path)
            else:
                result=d.check(path)
                self.assertEqual((result['push_cap'],result['install_cap'],result['total_seconds']),
                                 (0,1,600))
            client.assert_not_called()


if __name__=='__main__':unittest.main()
