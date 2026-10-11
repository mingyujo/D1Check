import hashlib
import tempfile
from pathlib import Path
import unittest
import zipfile
from tools import d1_research_originals as originals


class RestoreTests(unittest.TestCase):
    def fixture(self, root):
        raw=b'{"response_ns":123,"status":"unfinished"}\n'
        digest=hashlib.sha256(raw).hexdigest();archive=root/'part.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as out:out.writestr('objects/'+digest,raw)
        return dict(schema=1,assets=[dict(name=archive.name,bytes=archive.stat().st_size,sha256=originals.digest_file(archive))],
                    files=[dict(namespace='workspace',path='output/run/progress.jsonl',bytes=len(raw),sha256=digest,asset=archive.name,member='objects/'+digest)])

    def test_original_bytes_and_existing_file_preserved(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);manifest=self.fixture(root);dest=root/'restored'
            first=originals.restore(manifest,root,dest)
            second=originals.restore(manifest,root,dest)
            self.assertEqual(first['restored_files'],1);self.assertEqual(second['reused_files'],1)
            self.assertEqual(first['new_learning'],0);self.assertEqual(first['new_device_commands'],0)

    def test_traversal_drive_path_and_existing_drift_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);manifest=self.fixture(root)
            for path in ['../outside','C:/outside','/outside','ok/../../outside']:
                with self.assertRaises(ValueError):originals.safe_target(root,path)
            dest=root/'restored';originals.restore(manifest,root,dest)
            target=dest/'workspace/output/run/progress.jsonl';target.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'overwrite prohibited'):originals.restore(manifest,root,dest)
            self.assertEqual(target.read_bytes(),b'changed')

    def test_corrupt_archive_fails_before_restore(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);manifest=self.fixture(root);(root/'part.zip').write_bytes(b'bad')
            with self.assertRaises(ValueError):originals.restore(manifest,root,root/'restored')
            self.assertFalse((root/'restored').exists())


if __name__=='__main__':unittest.main()
