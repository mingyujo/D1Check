"""Only signature/recovery control-flow PC tests; no ADB, keys or real APK writes."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch

from tools import d1_apk_identity as a
from tools import d1_arrival_timing_calibration as c
from tools import d1_arrival_timing_calibration_device as d
from tools import test_d1_arrival_timing_calibration as calibration_fixture


class SigningTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.apk = self.root / 'candidate.apk'
        self.apk.write_bytes(b'synthetic-not-an-apk')
        self.identity = dict(package=d.legacy.PACKAGE, version_code=1,
                             signer_sha256='a'*64, apk_sha256=c.p.digest(self.apk))
        self.plan = dict(apk_path=str(self.apk), device_fingerprint='synthetic',
                         _plan_file=str(self.apk), apk_preflight=dict(candidate=self.identity,
                         toolchain={}, tool_sha256={}))

    def fake_device(self):
        device = Mock()
        device.identify.return_value = {'fingerprint': 'synthetic'}
        device.call.return_value = SimpleNamespace(stdout=b'package:/data/app/~~x/y/base.apk\n')
        return device

    def test_identity_parser_verifies_signature_and_distinguishes_file_hash(self):
        tools = dict(java='java', apksigner='apksigner.jar', aapt2='aapt2')
        cert = 'Number of signers: 1\nSigner #1 certificate SHA-256 digest: ' + 'a'*64
        package = "package: name='" + d.legacy.PACKAGE + "' versionCode='1'"
        with patch.object(a.subprocess, 'run', side_effect=[SimpleNamespace(stdout=cert), SimpleNamespace(stdout=package)]) as proc:
            self.assertEqual(a.inspect(self.apk, tools), self.identity)
            self.assertIn('verify', proc.call_args_list[0].args[0])
        with patch.object(a.subprocess, 'run', side_effect=RuntimeError('invalid signature')):
            with self.assertRaisesRegex(RuntimeError, 'invalid signature'):
                a.inspect(self.apk, tools)

    def test_mismatch_downgrade_package_unknown_fail_closed(self):
        for field, value in [('signer_sha256','b'*64), ('version_code',2), ('package','other')]:
            installed = dict(self.identity, **{field:value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                a.compatible(self.identity, installed, self.identity)
        with self.assertRaisesRegex(ValueError, 'frozen'):
            a.compatible(dict(self.identity, apk_sha256='wrong'), self.identity, self.identity)
        a.compatible(self.identity, dict(self.identity, apk_sha256='older-binary'), self.identity)

    def test_preflight_is_read_only_and_receipt_has_zero_consumption(self):
        device = self.fake_device()
        with patch.object(a, 'inspect', return_value=self.identity):
            result = a.preflight(device, self.plan, self.root/'preflight')
        self.assertEqual(result['status'], 'PREFLIGHT_COMPATIBLE_NOT_INSTALLED')
        self.assertFalse(result['phase_consumed'])
        self.assertEqual([x.args[:2] for x in device.call.call_args_list], [('shell','pm'),('pull','/data/app/~~x/y/base.apk')])
        with self.assertRaises(FileExistsError):
            a.preflight(device, self.plan, self.root/'preflight')

    def test_failed_or_unavailable_preflight_preserves_failure(self):
        for name in ('mismatch','unknown','split'):
            device = self.fake_device()
            if name == 'split':
                device.call.return_value.stdout = b'package:/data/app/x/base.apk\npackage:/data/app/x/split.apk\n'
            observations = [self.identity, dict(self.identity, signer_sha256='b'*64)]
            if name == 'unknown': observations = [RuntimeError('cannot inspect')]
            with patch.object(a, 'inspect', side_effect=observations), self.assertRaises((ValueError,RuntimeError)):
                a.preflight(device, self.plan, self.root/name)
            receipt = c.p.read(self.root/name/'preflight.json')
            self.assertEqual(receipt['status'], 'PREFLIGHT_FAILED')
            self.assertEqual((receipt['install_attempts'],receipt['session_attempts'],receipt['phase_consumed']),(0,0,False))

    def runner_plan(self):
        plan = dict(self.plan, experiment_id='ARRIVAL-TIMING-CAL-02', protocol=c.PROTOCOL,
                    registry=str(self.root/'registry'), apk_sha256=c.p.digest(self.apk), host_phase_wall_seconds=3600)
        path=self.root/'plan.json'; c.write_new(path,plan)
        return path,plan

    def test_runner_checks_before_claim_or_install_and_old_stop_blocks_read(self):
        path,plan=self.runner_plan()
        with patch.object(c,'check'), patch.object(a,'preflight',side_effect=ValueError('mismatch')), patch.object(c,'claim') as claim, patch.object(d.legacy,'Device') as device:
            with self.assertRaisesRegex(RuntimeError,'not consumed'):
                d.run(path,'development',self.root/'run','adb','serial',16,c.p.digest(path))
            claim.assert_not_called()
            device.return_value.call.assert_not_called()
        registry=Path(plan['registry']);registry.mkdir();c.write_new(registry/'development_stopped.json',{'old':'preserve'})
        before=(registry/'development_stopped.json').read_bytes()
        with patch.object(c,'check'), patch.object(d.legacy,'Device') as device, self.assertRaisesRegex(ValueError,'no restart'):
            d.run(path,'development',self.root/'run','adb','serial',16,c.p.digest(path))
        device.assert_not_called(); self.assertEqual(before,(registry/'development_stopped.json').read_bytes())

    def test_install_failure_is_phase_failure_but_zero_session_attempts(self):
        path,plan=self.runner_plan()
        device=self.fake_device();device.call.side_effect=RuntimeError('install failed')
        with patch.object(c,'check'), patch.object(a,'preflight',return_value={}), patch.object(d.legacy,'Device',return_value=device), patch.object(d,'cleanup',return_value={'status':'completed'}):
            with self.assertRaisesRegex(RuntimeError,'install failed'):
                d.run(path,'development',self.root/'run','adb','serial',16,c.p.digest(path))
        self.assertTrue((self.root/'run/install_attempt.json').exists())
        self.assertEqual(c.p.read(self.root/'run/stopped.json')['attempts'],0)
        self.assertTrue((Path(plan['registry'])/'development_consumed.json').exists())

    def test_recovery_plan_new_ids_same_budget_no_adb_or_measurements(self):
        fixture=calibration_fixture.CalibrationTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        parent_path=fixture.prepare(True);parent=c.p.read(parent_path)
        registry=Path(parent['registry']);registry.mkdir(parents=True)
        stopped=registry/'development_stopped.json';c.write_new(stopped,dict(plan_sha256=c.p.digest(parent_path)))
        old_bytes=parent_path.read_bytes()
        new_apk=fixture.root/'new.apk';new_apk.write_bytes(b'synthetic-new-signature')
        build=fixture.root/'resigned.json';c.write_new(build,dict(status='built_not_device_verified',source_code=c.code_identity(),apk_sha256=c.p.digest(new_apk)))
        identity=dict(self.identity,apk_sha256=c.p.digest(new_apk))
        binding=dict(parent_plan=str(parent_path),parent_plan_sha256=c.p.digest(parent_path),parent_stopped_sha256=c.p.digest(stopped),apk_preflight=dict(candidate=identity,toolchain={},tool_sha256={}))
        with patch.object(a,'inspect',return_value=identity), patch.object(d.legacy,'Device',side_effect=AssertionError('ADB forbidden')):
            c.prepare(fixture.source,fixture.root/'recovery',new_apk,build,binding)
            result=c.check(fixture.root/'recovery/calibration_plan.json')
        child=c.p.read(fixture.root/'recovery/calibration_plan.json')
        self.assertEqual((result['sessions'],result['diagnostic_requests'],result['warmup_calls']),(16,64,128))
        self.assertEqual(child['experiment_id'],'ARRIVAL-TIMING-CAL-02')
        self.assertNotEqual(child['registry'],parent['registry'])
        self.assertFalse({e['session_id'] for e in child['entries']} & {e['session_id'] for e in parent['entries']})
        self.assertEqual([(e['task'],e['backend'],e['priority'],e['phase']) for e in child['entries']],[(e['task'],e['backend'],e['priority'],e['phase']) for e in parent['entries']])
        self.assertEqual(parent_path.read_bytes(),old_bytes)
        self.assertFalse(Path(child['registry']).exists())


if __name__ == '__main__':
    unittest.main()
