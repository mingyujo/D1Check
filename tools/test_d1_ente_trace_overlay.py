import re
import tempfile
import unittest
from pathlib import Path
from tools.d1_ente_trace_overlay import instrument, prepare, replace_once, IMPORT


class OverlayTest(unittest.TestCase):
    # Explicit fixture path: no download, build or device access from tests.
    source_dir = None

    def originals(self):
        if self.source_dir is None:
            self.skipTest('requires pinned external source directory')
        return {p.name: p.read_text(encoding='utf-8')
                for p in self.source_dir.glob('*.dart')}

    def test_only_observation_changes(self):
        original = self.originals()
        changed = instrument(original)
        for name, text in changed.items():
            self.assertEqual(text.count(IMPORT), 1)
            restored = text.replace(IMPORT, '', 1)
            restored = re.sub(r'^ +D1BaselineTrace.emit\([^\n]+\);\n', '', restored,
                              flags=re.MULTILINE)
            restored = re.sub(r'D1BaselineTrace.finish\(runControl, ([\w.]+)\)',
                              r'\1', restored)
            self.assertEqual(restored, original[name])
        self.assertNotIn('compute_controller.dart', changed)
        self.assertNotIn('device_health_policy.dart', changed)

    def test_original_catch_and_finally_preserved(self):
        text = instrument(self.originals())['ml_service.dart']
        self.assertIn('_logger.severe("runAllML failed", e, s);', text)
        self.assertEqual(text.count('D1BaselineTrace.emit(control, "indexing_enter")'), 1)
        self.assertEqual(text.count('D1BaselineTrace.emit(control, "indexing_returned")'), 1)
        self.assertIn('computeController.releaseCompute(ml: true);', text)

    def test_ambiguous_anchor_rejected(self):
        with self.assertRaises(ValueError): replace_once('a a', 'a', 'b')
        with self.assertRaises(ValueError): replace_once('b', 'a', 'b')

    def test_hash_mismatch_creates_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);(root/'compute_controller.dart').write_text('changed')
            with self.assertRaises(ValueError): prepare(root, root/'output')
            self.assertFalse((root/'output').exists())

    def test_existing_output_rejected_and_source_unchanged(self):
        self.originals()
        before = {p.name:p.read_bytes() for p in self.source_dir.glob('*.dart')}
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileExistsError): prepare(self.source_dir, Path(folder))
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.source_dir.glob('*.dart')})


if __name__ == '__main__':
    import sys
    OverlayTest.source_dir = Path(sys.argv.pop(1))
    unittest.main()
