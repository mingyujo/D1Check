import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from d1_a24_confirm_followup_window import select_remaining, FollowupClient, BoundedClient
from d1_a24_revision02_suite import draft_plan
from d1_a24_laptop_validator import ValidationError


class FollowupCases(unittest.TestCase):
    def setUp(self):
        self.plan,_=draft_plan('A24R02-SUITE-FOLLOWUP-PC-ONLY-CONFIRM')
        self.ledger=dict(cap=81,consumed_before_new_confirm=41,total_consumed=45,remaining=36,
            records=[dict(session_id=r['session_id'],APP_launches=int(i<4),
                          outcome='COMPLETE_TRACE_RECOVERED' if i<4 else 'NOT_ATTEMPTED',START=i<4)
                     for i,r in enumerate(self.plan['sessions'])])
        self.window={'registered_session_ids':[r['session_id'] for r in self.plan['sessions'][4:]]}

    def test_exact36_unconsumed(self):
        self.assertEqual(len(select_remaining(self.plan,self.window,self.ledger)),36)

    def test_consumed_skipped_reordered_rejected(self):
        for selected in (self.plan['sessions'][:4],self.plan['sessions'][5:8],self.plan['sessions'][4:8][::-1]):
            with self.assertRaises(ValidationError):
                select_remaining(self.plan,{'registered_session_ids':[r['session_id'] for r in selected]},self.ledger)

    def test_inconsistent_budget_rejected(self):
        for patch in ({'cap':82},{'total_consumed':44},{'remaining':40}):
            with self.assertRaises(ValidationError):select_remaining(self.plan,self.window,self.ledger|patch)

    def test_hidden_attempt_not_reused(self):
        ledger=copy.deepcopy(self.ledger);ledger['records'][4].update(APP_launches=1,START=True,outcome='FAILED_PRESERVED')
        ledger.update(total_consumed=46,remaining=35)
        with self.assertRaises(ValidationError):select_remaining(self.plan,self.window,ledger)

    def test_app_intent_written_before_send_and_second_send_blocked(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'reservations'/'testsid').mkdir(parents=True)
            client=FollowupClient.__new__(FollowupClient)
            client.global_root=root;client.ledger={'total_consumed':45,'cap':81};client.active_sid='testsid'
            client.check_window=lambda phase:True
            marker=root/'reservations'/'testsid'/'APP_LAUNCH_INTENT.json'
            def sent(*args,**kwargs):
                self.assertTrue(marker.exists())
                return b''
            with patch.object(BoundedClient,'command',side_effect=sent) as call:
                client.command('shell','am','start','--es','session_id','testsid')
                with self.assertRaises(ValidationError):client.command('shell','am','start','--es','session_id','testsid')
                self.assertEqual(call.call_count,1)

    def test_full_budget_blocks_app_before_send(self):
        with tempfile.TemporaryDirectory() as folder:
            client=FollowupClient.__new__(FollowupClient)
            client.global_root=Path(folder);client.ledger={'total_consumed':81,'cap':81};client.active_sid='testsid'
            with patch.object(BoundedClient,'command') as call:
                with self.assertRaises(ValidationError):client.command('shell','am','start','--es','session_id','testsid')
                call.assert_not_called()


if __name__=='__main__':unittest.main()
