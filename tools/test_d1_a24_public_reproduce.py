import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from d1_a24_public_reproduce import verified_members


class ArchiveIntegrity(unittest.TestCase):
    def test_all_member_bytes_must_match_even_if_outer_archive_is_rehashed(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'block.zip';b=b'original'
            index={'members':[{'path':'raw/events.jsonl','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}]}
            with zipfile.ZipFile(p,'x') as z:z.writestr('raw/events.jsonl',b);z.writestr('FILE_SHA256.json',json.dumps(index))
            digest=hashlib.sha256(p.read_bytes()).hexdigest();self.assertEqual(verified_members(p,digest)['raw/events.jsonl'],b)
            q=Path(d)/'tampered.zip'
            with zipfile.ZipFile(q,'x') as z:z.writestr('raw/events.jsonl',b'changed!');z.writestr('FILE_SHA256.json',json.dumps(index))
            with self.assertRaises(ValueError):verified_members(q,hashlib.sha256(q.read_bytes()).hexdigest())
            with self.assertRaises(ValueError):verified_members(p,'0'*64)


if __name__=='__main__':unittest.main()
