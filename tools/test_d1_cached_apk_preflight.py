import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tools import d1_apk_identity as apk


class CachedPreflightTests(unittest.TestCase):
    def test_current_hash_proves_inspected_cached_bytes_without_pull(self):
        for same in (True,False):
            with self.subTest(same=same),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);cache=root/'cached.apk';cache.write_bytes(b'fixture APK');file=root/'plan.json';file.write_text('{}')
                sha=hashlib.sha256(cache.read_bytes()).hexdigest()
                identity=dict(package='fixture.package',version_code=1,signer_sha256='c'*64,apk_sha256=sha)
                plan=dict(_plan_file=str(file),device_fingerprint='fixture',apk_path='candidate',apk_preflight=dict(toolchain={},tool_sha256={},candidate=identity),cached_installed_apk=dict(path=str(cache),sha256=sha))
                calls=[]
                def call(*args,**kw):
                    calls.append(args)
                    return SimpleNamespace(stdout=b'package:/data/app/fixture/base.apk\n' if args[:3]==('shell','pm','path') else ((sha if same else '0'*64)+'  /data/app/fixture/base.apk\n').encode())
                device=SimpleNamespace(call=call,identify=lambda expected:{},deadline=999999999)
                with patch.object(apk,'inspect',return_value=identity) as inspect:
                    if same:self.assertEqual(apk.preflight(device,plan,root/'output')['installed'],identity);self.assertEqual(inspect.call_count,2)
                    else:
                        with self.assertRaisesRegex(ValueError,'current installed APK differs'):apk.preflight(device,plan,root/'output')
                        self.assertEqual(inspect.call_count,1)
                self.assertEqual(len(calls),2);self.assertFalse(any(c[0]=='pull' for c in calls))


if __name__=='__main__':unittest.main()
