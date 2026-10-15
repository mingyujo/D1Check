import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch
from d1_a24_live_publish import publish, BRANCH, publication_signature


class PublishCases(unittest.TestCase):
    def test_stage_and_APP_start_publish_before_any_closed_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);root=p/'run';registry=p/'global';sid='new-session'
            spec=[('SUP12','unused',{'run_root':str(root),'supplement_global_root':str(registry)},None,[{'session_id':sid}])]
            before=publication_signature(spec);root.mkdir();registry.mkdir()
            (registry/'ACTIVE_OWNER.json').write_text('{}')
            started=publication_signature(spec);self.assertNotEqual(before,started)
            reservation=registry/'reservations'/sid;reservation.mkdir(parents=True)
            (reservation/'APP_LAUNCH_INTENT.json').write_text('{}')
            intent=publication_signature(spec);self.assertNotEqual(started,intent)
            self.assertFalse(list(root.glob('*.outcome.json')))
            (root/'WINDOW_STOPPED.json').write_text('{}');(registry/'ACTIVE_OWNER.json').unlink()
            self.assertNotEqual(intent,publication_signature(spec))

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
