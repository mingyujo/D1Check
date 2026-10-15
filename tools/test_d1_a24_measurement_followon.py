from pathlib import Path
import tempfile
import unittest

from d1_a24_measurement_followon import closed_before_followon, parser_proved
from d1_a24_laptop_validator import ValidationError, sha256


class FollowonCases(unittest.TestCase):
    def test_stop_receipt_alone_cannot_bypass_active_previous_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);root=p/'A24R02C10';root.mkdir();owner=p/'A24R02C10_GLOBAL';owner.mkdir()
            job={'run_root':str(root)}
            self.assertFalse(closed_before_followon(job))
            (root/'WINDOW_STOPPED.json').write_text('{}')
            (owner/'ACTIVE_OWNER.json').write_text('{}')
            self.assertFalse(closed_before_followon(job))
            (owner/'ACTIVE_OWNER.json').unlink()
            self.assertTrue(closed_before_followon(job))

    def test_actual_parser_must_be_exact_test_with_no_skips_or_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'parser.xml'
            for failure,skip,name in [('1','0','twelveFreshSupplementManifestsUseTheUnchangedActualParser'),
                                      ('0','1','twelveFreshSupplementManifestsUseTheUnchangedActualParser'),
                                      ('0','0','someOtherTest')]:
                p.write_text('<testsuite tests="1" failures="'+failure+'" errors="0" skipped="'+skip+'"><testcase name="'+name+'"/></testsuite>')
                with self.assertRaises(ValidationError):parser_proved(p,sha256(p))
            p.write_text('<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="twelveFreshSupplementManifestsUseTheUnchangedActualParser"/></testsuite>')
            parser_proved(p,sha256(p))
            with self.assertRaises(ValidationError):parser_proved(p,'a'*64)


if __name__=='__main__':unittest.main()
