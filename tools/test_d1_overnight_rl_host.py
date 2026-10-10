"""Saving failures must not trigger new native execution or unbounded retry."""
import unittest
from unittest.mock import patch
from tools import d1_overnight_rl_amount as x

class HostSave(unittest.TestCase):
    def test_transient_windows_rename_retry(self):
        with patch.object(x.x,'write',side_effect=[PermissionError('reader'),None]) as writer,patch.object(x.time,'sleep') as sleep:
            x.write('unused',{'progress':1})
            self.assertEqual(writer.call_count,2);sleep.assert_called_once_with(.05)
    def test_retry_is_bounded_and_error_survives(self):
        with patch.object(x.x,'write',side_effect=PermissionError('persistent')) as writer,patch.object(x.time,'sleep') as sleep:
            with self.assertRaises(PermissionError):x.write('unused',{})
            self.assertEqual(writer.call_count,20);self.assertEqual(sleep.call_count,19)

if __name__=='__main__':unittest.main()
