from pathlib import Path
import tempfile
import unittest
from tools import d1_research_originals_tests as paths


class MetadataPathTests(unittest.TestCase):
    def test_relocation_is_idempotent_and_leaves_numeric_data_unchanged(self):
        with tempfile.TemporaryDirectory() as name:
            workspace=Path(name)/'workspace';external=Path(name)/'external'
            source=dict(path='C:/Users/example/AndroidStudioProjects/D1Check-model02b/output/run/validated.json',
                        watts=[1.2,3.4],deadline_ns=1500000000,status=False,model_sha256='a'*64)
            mapped=paths.relocated_metadata(source,workspace,external)
            self.assertEqual(paths.relocated_metadata(mapped,workspace,external),mapped)
            self.assertEqual(mapped['watts'],source['watts'])
            self.assertEqual(mapped['deadline_ns'],source['deadline_ns'])
            self.assertEqual(mapped['status'],source['status'])
            self.assertEqual(mapped['model_sha256'],source['model_sha256'])
            self.assertEqual(Path(mapped['path']),workspace/'output/run/validated.json')

    def test_historical_parent_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            root=Path(name)
            with self.assertRaises(ValueError):
                paths.relocated_string('C:/Users/example/D1Check-model02b/../../outside',root/'workspace',root/'external')


if __name__=='__main__':unittest.main()
