import struct
import tempfile
from pathlib import Path
import unittest
from tools.d1_classification_reference import checked_input, sha


class ClassificationReferenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.image = Path(self.temp.name)/'input.png'
        chunk = lambda kind, value: struct.pack('>I', len(value))+kind+value+b'\0'*4
        self.png = b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR', b'\0'*13)+chunk(b'IDAT', b'x')+chunk(b'IEND', b'')
        self.image.write_bytes(self.png)

    def test_read_bytes_are_bound_to_expected_digest(self):
        self.assertEqual(checked_input(self.image, sha(self.png)), self.png)

    def test_old_input_cannot_be_assigned_new_manifest_hash(self):
        with self.assertRaisesRegex(ValueError, 'actual input bytes'):
            checked_input(self.image, sha(self.png+b'new canonical bytes'))

    def test_missing_or_malformed_expected_digest_rejected(self):
        for value in (None, '', '0'*63, 'G'*64):
            with self.assertRaises(ValueError):
                checked_input(self.image, value)

    def test_matching_hash_does_not_authorize_noncanonical_input(self):
        for data in (b'JPEG', self.png+b'extra'):
            self.image.write_bytes(data)
            with self.assertRaises(ValueError):
                checked_input(self.image, sha(data))


if __name__ == '__main__':
    unittest.main()
