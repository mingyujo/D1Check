import tempfile
import unittest
from pathlib import Path
from d1_a24_confirmation_visit_merge import copy_exact


class ExactCopies(unittest.TestCase):
    def test_identical_collision_keeps_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=root/'a';b=root/'b';a.write_bytes(b'raw\r\n')
            copy_exact(a,b);copy_exact(a,b)
            self.assertEqual(b.read_bytes(),b'raw\r\n')

    def test_conflicting_copy_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);a=root/'a';b=root/'b';a.write_bytes(b'new');b.write_bytes(b'old')
            with self.assertRaises(ValueError):copy_exact(a,b)
            self.assertEqual(b.read_bytes(),b'old')


if __name__=='__main__':unittest.main()
