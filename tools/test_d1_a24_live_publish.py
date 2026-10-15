import unittest
from unittest.mock import patch
from d1_a24_live_publish import publish, BRANCH


class PublishCases(unittest.TestCase):
    def test_other_branch_stops_before_any_read_stage_or_push(self):
        with patch('d1_a24_live_publish.git',return_value='unrelated-user-branch') as git, \
             patch('d1_a24_live_publish.refresh') as refresh:
            with self.assertRaises(RuntimeError):publish()
            self.assertEqual(git.call_count,1);refresh.assert_not_called()

    def test_foreign_staged_changes_are_never_committed_or_reset(self):
        with patch('d1_a24_live_publish.git',side_effect=[BRANCH,'user-owned.txt']) as git, \
             patch('d1_a24_live_publish.refresh') as refresh:
            with self.assertRaises(RuntimeError):publish()
            self.assertEqual(git.call_count,2);refresh.assert_not_called()


if __name__=='__main__':unittest.main()
