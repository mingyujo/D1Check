import copy
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from d1_a24_confirm_after_diagnostic import select_remaining, FollowupClient, BoundedClient,check_history
from d1_a24_revision02_suite import draft_plan
from d1_a24_laptop_validator import ValidationError,sha256,PROTOCOL
from d1_a24_laptop_control import atomic_json


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

    def test_after_nine_exact31(self):
        ledger=copy.deepcopy(self.ledger)
        for row in ledger['records'][:9]:row.update(APP_launches=1,START=True,outcome='COMPLETE_TRACE_RECOVERED')
        ledger.update(total_consumed=50,remaining=31)
        window={'registered_session_ids':[r['session_id'] for r in self.plan['sessions'][9:]]}
        self.assertEqual(len(select_remaining(self.plan,window,ledger)),31)

    def test_stop_flag_blocks_only_new_app(self):
        with tempfile.TemporaryDirectory() as folder:
            client=FollowupClient.__new__(FollowupClient);client.job_run_root=folder
            Path(folder,'STOP_AFTER_CURRENT.json').write_text('{}')
            with patch.object(BoundedClient,'check_window',return_value=True) as parent:
                for phase in ['NEW_SESSION','APP_CREATE']:
                    with self.assertRaises(ValidationError):client.check_window(phase)
                self.assertTrue(client.check_window('MAIN_START'))
                self.assertTrue(client.check_window('RPC'))
                self.assertEqual(parent.call_count,2)

    def test_proven_preAPP_binding_preserved_but_start_intent_or_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)/'visit';root.mkdir();sid='unstarted';glob=Path(folder)/'global'
            plan=Path(folder)/'plan.json';atomic_json(plan,{'plan_id':'PLAN'})
            atomic_json(root/'WINDOW_STOPPED.json',{'external_host_stop':True,'active_APPs_at_stop':0,'reason':'USER_PAUSE_AFTER_CLOSED_BEFORE_CURRENT_RESPONSE_DIAGNOSTIC'})
            bd=root/'bindings'/sid;bd.mkdir(parents=True);f=bd/'session_manifest.json';f.write_text('{}')
            binding={'previous_visits':[{'root':str(root),'stop_sha256':sha256(root/'WINDOW_STOPPED.json')}],
              'previous_global_reservation_roots':[str(glob)],'unstarted_preAPP_bindings':{sid:{'visit_root':str(root),'binding_file_sha256':{'session_manifest.json':sha256(f)}}}}
            ledger={'records':[{'session_id':sid,'APP_launches':0}]};job={'plan':str(plan)}
            check_history(job,binding,ledger)
            f.write_text('{"changed":true}')
            with self.assertRaises(ValidationError):check_history(job,binding,ledger)
            f.write_text('{}')
            registry=root/'registry'/PROTOCOL/'PLAN'/sid;registry.mkdir(parents=True)
            with self.assertRaises(ValidationError):check_history(job,binding,ledger)
            registry.rmdir()
            (glob/'reservations'/sid).mkdir(parents=True)
            with self.assertRaises(ValidationError):check_history(job,binding,ledger)

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
