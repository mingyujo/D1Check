import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import d1_a24_confirm_remaining as mod
from d1_a24_laptop_validator import ValidationError,PROTOCOL,sha256
from d1_a24_revision02_suite import draft_plan


class ScopeCases(unittest.TestCase):
    def setUp(self):
        self.plan,_=draft_plan('A24R02-SUITE-CONFIRM-REMAINING-TEST')
        self.ledger={'cap':81,'consumed_before_new_confirm':41,'total_consumed':58,'remaining':23,
            'records':[dict(session_id=r['session_id'],APP_launches=int(i<17),START=i<17,
                            outcome='COMPLETE_TRACE_RECOVERED' if i<17 else 'NOT_ATTEMPTED') for i,r in enumerate(self.plan['sessions'])]}

    def test_exact_23_and3368_requests_unchanged(self):
        rows=mod.exact_scope(self.plan,self.ledger)
        self.assertEqual(rows,self.plan['sessions'][17:]);self.assertEqual(sum(r['request_count'] for r in rows),3368)

    def test_replay_hole_budget_and_reordered_ledger_rejected(self):
        for kind in ['replay','hole','budget','order']:
            x=copy.deepcopy(self.ledger)
            if kind=='replay':x['records'][0]['APP_launches']=2
            if kind=='hole':x['records'][16],x['records'][17]=x['records'][17],x['records'][16]
            if kind=='budget':x['remaining']=24
            if kind=='order':x['records']=x['records'][::-1]
            with self.subTest(kind=kind),self.assertRaises(ValidationError):mod.exact_scope(self.plan,x)

    def test_draft_or_mock_or_insufficient_time_never_admitted(self):
        now=dt.datetime.now(dt.timezone.utc)
        good={'execution_authorized':True,'hard_stop_UTC':(now+dt.timedelta(hours=1)).isoformat(),
              'work_stop_UTC':(now+dt.timedelta(hours=1,minutes=5)).isoformat()}
        mod.validate_time_window(good,False)
        for preparation,w in [(True,good),(False,{**good,'execution_authorized':False}),
                              (False,{**good,'PC_MOCK_ONLY':True}),
                              (False,{**good,'hard_stop_UTC':(now+dt.timedelta(minutes=20)).isoformat()})]:
            with self.assertRaises(ValidationError):mod.validate_time_window(w,preparation)

    def test_explicit_permutation_defers_one_slot_without_losing_requests(self):
        ids=[r['session_id'] for r in self.plan['sessions']]
        order=ids[:17]+ids[18:]+ids[17:18]
        rows=mod.exact_scope(self.plan,self.ledger,order)
        self.assertEqual([r['session_id'] for r in rows],order[17:])
        self.assertEqual(sum(r['request_count'] for r in rows),3368)
        after=copy.deepcopy(self.ledger);after.update(total_consumed=59,remaining=22)
        after['records'][18].update(APP_launches=1,START=True,outcome='COMPLETE_TRACE_RECOVERED')
        self.assertEqual(mod.exact_scope(self.plan,after,order)[0]['session_id'],ids[19])
        with self.assertRaises(ValidationError):mod.exact_scope(self.plan,after)

    def test_permutation_cannot_drop_duplicate_add_or_reorder_used_slots(self):
        ids=[r['session_id'] for r in self.plan['sessions']]
        for order in [ids[:-1],ids[:-1]+ids[:1],ids[:-1]+['foreign'],ids[:16]+ids[17:18]+ids[16:17]+ids[18:]]:
            with self.assertRaises(ValidationError):mod.exact_scope(self.plan,self.ledger,order)

    def test_draft_execute_fails_before_inspection_or_device(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'w.json';p.write_text(json.dumps({'execution_authorized':False,'hard_stop_UTC':None,'work_stop_UTC':None}))
            with (patch.object(mod,'history_inventory',side_effect=AssertionError('should fail first')),
                  patch.object(mod.executor,'execute',side_effect=AssertionError('must not execute'))):
                with self.assertRaises(ValidationError):mod.inspect({'window_file':str(p),'preparation_only':True},runtime=True)

    def test_binding_window_only_keeps_draft_and_does_not_start_device(self):
        with tempfile.TemporaryDirectory() as t:
            b=Path(t);contract=b/'contract.json';contract.write_text('{}')
            job={'revision_contract_file':str(contract),'run_root':str(b/'device'/'device_root')}
            rows=[{'session_id':'first'},{'session_id':'second'}]
            old={'execution_authorized':False,'hard_stop_UTC':None,'work_stop_UTC':None}
            binding={'global_reservation_root':str(b/'state'/'global'),'carry_references':[]}
            now=dt.datetime.now(dt.timezone.utc)
            with (patch.object(mod,'inspect',return_value=(rows,old,{},binding)),
                  patch.object(mod,'verify_authorizations',return_value=[{'PC_MOCK_only':True}]),
                  patch.object(mod.executor,'execute') as execute):
                result=mod.bind_window(job,b/'new_visit',(now+dt.timedelta(hours=1)).isoformat(),
                                       (now+dt.timedelta(hours=1,minutes=5)).isoformat(),1)
            self.assertFalse(old['execution_authorized']);self.assertFalse(Path(result['run_root']).exists())
            window=json.loads(Path(result['window_file']).read_text())
            self.assertEqual(window['registered_session_ids'],['first']);self.assertTrue(window['execution_authorized'])
            execute.assert_not_called()


class HistoryCases(unittest.TestCase):
    def test_prior_APP0_passive_binding_is_preserved_after_later_actual_APP(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);spec,plan,ledger,old,new,_=self.fixture(base)
            passive=base/'passive';(passive/'bindings'/'s').mkdir(parents=True)
            (passive/'s.preapp_stop.json').write_text(json.dumps({'APP':0,'binding_created':True,'reason':'USER_STOP_AFTER_CURRENT'}))
            (passive/'STOP_AFTER_CURRENT.json').write_text('{}')
            stop=passive/'WINDOW_STOPPED.json';stop.write_text(json.dumps({'reason':'PRE_APP_COOLDOWN_STOP','new_APP_intents':0,'outcomes':[]}))
            spec['previous_visits'].insert(1,{'root':str(passive),'stop_sha256':sha256(stop)})
            inventory,hits=mod.history_inventory(spec,plan,ledger)
            self.assertEqual(hits['s'],[new]);self.assertIn('passive/s.preapp_stop.json',inventory)
            (passive/'s.preapp_stop.json').write_text(json.dumps({'APP':1,'binding_created':True,'reason':'USER_STOP_AFTER_CURRENT'}))
            with self.assertRaises(ValidationError):mod.history_inventory(spec,plan,ledger)

    def test_consumed_prestart_failure_requires_closed_same_session_evidence(self):
        from test_d1_a24_failed_prestart_evidence import FailedPrestartCases
        from d1_a24_failed_prestart_evidence import verify_failed_prestart
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);root=base/'failed';root.mkdir();g=base/'global';g.mkdir()
            reg,recovered=FailedPrestartCases().fixture(root)
            plan={'plan_id':'p','sessions':[{'session_id':'s','request_count':2}]}
            proof=verify_failed_prestart(root,plan,plan['sessions'][0],recovered,plan_sha256='a'*64)
            proof['own_device_process_absent']=True
            pp=recovered.parent/'CLOSED_FAILURE_RECOVERY.json';pp.write_text(json.dumps(proof))
            stop=root/'WINDOW_STOPPED.json';stop.write_text(json.dumps({'reason':'FAILED_ATTEMPT_PRESERVED'}))
            (root/'adb_commands.jsonl').write_text(json.dumps({'argv':['adb','shell','am','start','session_id','s']})+'\n')
            reservation=g/'reservations'/'s';reservation.mkdir(parents=True)
            (reservation/'APP_LAUNCH_INTENT.json').write_text('{}')
            spec={'previous_visits':[{'root':str(root),'stop_sha256':sha256(stop)}],
                  'previous_global_reservation_roots':[str(g)],'closed_failed_prestart_evidence':{
                      's':{'visit_root':str(root),'recovered_path':str(recovered),'proof_path':str(pp),'proof_sha256':sha256(pp)}}}
            ledger={'plan_sha256':'a'*64,'records':[{'session_id':'s','APP_launches':1,'START':False,
                    'outcome':'PRESTART_REJECT','failed_recovery_files_sha256':proof['recovered_files_sha256']}]}
            inventory,hits=mod.history_inventory(spec,plan,ledger)
            self.assertEqual(hits['s'],[root]);self.assertTrue(inventory)
            for kind in ['missing','foreign','changed_ledger','MAIN']:
                s=copy.deepcopy(spec);l=copy.deepcopy(ledger)
                if kind=='missing':s.pop('closed_failed_prestart_evidence')
                elif kind=='foreign':s['closed_failed_prestart_evidence']['s']['recovered_path']=str(base/'foreign')
                elif kind=='changed_ledger':l['records'][0]['failed_recovery_files_sha256']={}
                else:(reg/'START.json').write_text('{}')
                with self.subTest(kind=kind),self.assertRaises(ValidationError):mod.history_inventory(s,plan,l)
                if kind=='MAIN':(reg/'START.json').unlink()

    def fixture(self,base):
        sid='s';old=base/'old';new=base/'new';globalroot=base/'global';globalroot.mkdir()
        for root in [old,new]:root.mkdir();(root/'WINDOW_STOPPED.json').write_text('{}')
        registry=old/'registry'/PROTOCOL/'p'/sid;registry.mkdir(parents=True)
        (registry/'host_hal_partial.jsonl').write_bytes(b'')
        (registry/'PRESTART_REJECT.json').write_text(json.dumps({'START':False,'session_run_consumed':False}))
        raw=old/'raw'/sid;raw.mkdir(parents=True);(raw/'host_hal_partial.jsonl').write_bytes(b'')
        (old/'s.outcome.json').write_text(json.dumps({'APP_launch_intent':False}))
        raw=new/'raw'/sid;raw.mkdir(parents=True)
        (raw/'events.jsonl').write_text('{}\n');(raw/'journal_closed.json').write_text(json.dumps({'status':'SYNCED_AND_CLOSED'}))
        (new/'s.outcome.json').write_text(json.dumps({'status':'COMPLETE_TRACE_RECOVERED'}))
        (new/'adb_commands.jsonl').write_text(json.dumps({'argv':['adb','shell','am','start','session_id',sid]})+'\n')
        spec={'previous_visits':[{'root':str(r),'stop_sha256':sha256(r/'WINDOW_STOPPED.json')} for r in [old,new]],'previous_global_reservation_roots':[str(globalroot)]}
        ledger={'records':[{'session_id':sid,'APP_launches':1,'events_sha256':sha256(raw/'events.jsonl'),
                           'closed_sha256':sha256(raw/'journal_closed.json'),'outcome':'COMPLETE_TRACE_RECOVERED'}]}
        return spec,{'plan_id':'p','sessions':[{'session_id':sid}]},ledger,old,new,globalroot

    def test_two_preAPP_visits_and_unique_actual_execution_are_distinct(self):
        with tempfile.TemporaryDirectory() as t:
            spec,plan,ledger,old,new,_=self.fixture(Path(t));inventory,hits=mod.history_inventory(spec,plan,ledger)
            self.assertEqual(hits['s'],[new]);self.assertIn('old/s.outcome.json',inventory)

    def test_preAPP_sample_duplicate_APP_or_foreign_owner_rejected(self):
        for kind in ['sample','APP','owner','raw_changed']:
            with tempfile.TemporaryDirectory() as t:
                spec,plan,ledger,old,new,g=self.fixture(Path(t))
                if kind=='sample':(old/'raw'/'s'/'host_hal_partial.jsonl').write_text('{}')
                if kind=='APP':(old/'adb_commands.jsonl').write_text((new/'adb_commands.jsonl').read_text())
                if kind=='owner':(g/'ACTIVE_OWNER.json').write_text('{}')
                if kind=='raw_changed':(new/'raw'/'s'/'events.jsonl').write_text('changed')
                with self.subTest(kind=kind),self.assertRaises(ValidationError):mod.history_inventory(spec,plan,ledger)

    def test_missing_wrong_or_reselected_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);refs=base/'references';refs.mkdir()
            row={'session_id':'pending','reference_role':'MATCH_FIXED','reference_owner_session_id':'done','gate_block_id':'block'}
            ledger={'records':[{'session_id':'done','APP_launches':1}]};hits={'done':[base]};path=refs/'block.json'
            anchor={'block_id':'block','reference_session_id':'done','frozen_before_any_main_request':True,'outcome_inputs_used':False,'Tref_c':27.1}
            path.write_text(json.dumps(anchor));self.assertEqual(mod.carry_references([row],ledger,hits)[0]['Tref_c'],27.1)
            for key,value in [('reference_session_id','foreign'),('frozen_before_any_main_request',False),('outcome_inputs_used',True)]:
                path.write_text(json.dumps({**anchor,key:value}))
                with self.assertRaises(ValidationError):mod.carry_references([row],ledger,hits)

    def test_closed_passive_wait_rebound_preserves_no_APP_and_hashes(self):
        with tempfile.TemporaryDirectory() as t:
            b=Path(t);root=b/'passive';root.mkdir();g=b/'global';g.mkdir()
            binding=root/'bindings'/'s';binding.mkdir(parents=True)
            (binding/'gate.json').write_text('{}')
            (root/'s.preapp_stop.json').write_text(json.dumps({'APP':0,'binding_created':True,'reason':'USER_STOP_AFTER_CURRENT'}))
            (root/'STOP_AFTER_CURRENT.json').write_text(json.dumps({'reason':'EARLIER_USER_DEADLINE'}))
            (root/'pre_app_cooldown_v2').mkdir();cooling=root/'pre_app_cooldown_v2'/'s.jsonl';cooling.write_text('{}\n')
            stop=root/'WINDOW_STOPPED.json';stop.write_text(json.dumps({'reason':'PRE_APP_COOLDOWN_STOP','new_APP_intents':0,'outcomes':[]}))
            spec={'previous_visits':[{'root':str(root),'stop_sha256':sha256(stop)}],'previous_global_reservation_roots':[str(g)]}
            plan={'plan_id':'p','sessions':[{'session_id':'s'}]}
            ledger={'records':[{'session_id':'s','APP_launches':0}]}
            inventory,hits=mod.history_inventory(spec,plan,ledger)
            self.assertEqual(hits['s'],[])
            self.assertEqual(inventory['passive/pre_app_cooldown_v2/s.jsonl'],sha256(cooling))
            for kind in ['APP_intent','START','unknown_receipt','unknown_stop','APP_command']:
                with self.subTest(kind=kind):
                    if kind=='APP_intent':
                        p=g/'reservations'/'s';p.mkdir(parents=True);(p/'APP_LAUNCH_INTENT.json').write_text('{}')
                    elif kind=='START':
                        p=root/'registry'/PROTOCOL/'p'/'s';p.mkdir(parents=True);(p/'START.json').write_text('{}')
                    elif kind=='unknown_receipt':
                        p=root/'s.preapp_stop.json';original=p.read_bytes();p.write_text(json.dumps({'APP':0,'binding_created':True,'reason':'UNKNOWN_DELIVERY'}))
                    elif kind=='unknown_stop':
                        p=stop;original=p.read_bytes();p.write_text(json.dumps({'reason':'ERROR','new_APP_intents':0,'outcomes':[]}));spec['previous_visits'][0]['stop_sha256']=sha256(stop)
                    else:
                        p=root/'adb_commands.jsonl';p.write_text(json.dumps({'argv':['adb','shell','am','start','session_id','s']})+'\n')
                    with self.assertRaises(ValidationError):mod.history_inventory(spec,plan,ledger)
                    if kind in {'APP_intent','START'}:
                        for child in p.iterdir():child.unlink()
                        p.rmdir()
                    elif kind in {'unknown_receipt','unknown_stop'}:
                        p.write_bytes(original);spec['previous_visits'][0]['stop_sha256']=sha256(stop)
                    else:p.unlink()

    def test_closed_prefix_and_unlaunched_next_binding_remain_distinct(self):
        with tempfile.TemporaryDirectory() as t:
            spec,plan,ledger,old,root,g=self.fixture(Path(t))
            sid='pending';plan['sessions'].append({'session_id':sid});ledger['records'].append({'session_id':sid,'APP_launches':0})
            (root/'bindings'/sid).mkdir(parents=True)
            (root/(sid+'.preapp_stop.json')).write_text(json.dumps({'APP':0,'binding_created':True,'reason':'USER_STOP_AFTER_CURRENT'}))
            (root/'STOP_AFTER_CURRENT.json').write_text('{}')
            stop=root/'WINDOW_STOPPED.json'
            closed={'reason':'PRE_APP_COOLDOWN_STOP','new_APP_intents':1,
                'outcomes':[{'session_id':'s','APP_launch_intent':True}]}
            stop.write_text(json.dumps(closed));spec['previous_visits'][1]['stop_sha256']=sha256(stop)
            _,hits=mod.history_inventory(spec,plan,ledger);self.assertEqual(hits[sid],[])
            for bad in [{**closed,'new_APP_intents':0},
                        {**closed,'outcomes':[{'session_id':sid,'APP_launch_intent':True}]},
                        {**closed,'outcomes':[{'session_id':'s','APP_launch_intent':False}]}]:
                stop.write_text(json.dumps(bad));spec['previous_visits'][1]['stop_sha256']=sha256(stop)
                with self.assertRaises(ValidationError):mod.history_inventory(spec,plan,ledger)


class ReadOnlyCases(unittest.TestCase):
    def test_mutations_blocked_before_any_ADB_call(self):
        client=object.__new__(mod.ReadOnlyClient)
        with patch.object(mod.ReconnectingAdbClient,'command',return_value=b'') as call:
            for args in [('install','a.apk'),('push','x','y'),('shell','am','start'),('shell','settings','put','system','x','1'),
                         ('shell','run-as','pkg','mv','a','b'),('shell','dumpsys','thermalservice'),('shell','run-as','pkg','find','files','-delete')]:
                with self.assertRaises(ValidationError):client.command(*args)
            call.assert_not_called()
            client.command('shell','dumpsys','battery');self.assertEqual(call.call_count,1)

    def test_device_check_records_blockers_without_setting_changes_or_APP(self):
        class FakeClient:
            def __init__(self,*args,**kwargs):self.actual_calls=0
            def reconnect(self):pass
            def command(self,*args,**kwargs):
                self.actual_calls+=1
                if args[:2]==('shell','getprop'):return b'hardware' if args[2]=='ro.serialno' else b'firmware'
                if args[:2]==('shell','pidof'):return b''
                if args[:3]==('shell','pm','path'):return b'package:/data/app/mock/base.apk\n'
                if args[:2]==('shell','sha256sum'):return ('a'*64+'  base.apk\n').encode()
                if args==('shell','dumpsys','battery'):return b'AC powered: false\nUSB powered: true\nWireless powered: false\nlevel: 9\nscale: 100\n'
                if args[:3]==('shell','settings','get'):return b'81' if args[-1]=='screen_brightness' else b'0'
                if args==('shell','dumpsys','power'):return b'mWakefulness=Asleep'
                if args[:2]==('shell','run-as'):return b'files/a24_laptop_inputs/pending\n'
                raise AssertionError(args)
        with tempfile.TemporaryDirectory() as t:
            b=Path(t);(b/'target.json').write_text(json.dumps({'adb_serial':'mock','hardware_serial':'hardware','build_fingerprint':'firmware'}))
            (b/'apk.json').write_text(json.dumps({'package':'pkg','apk_sha256':'a'*64}))
            job={'device_registration':str(b/'target.json'),'apk_identity':str(b/'apk.json'),'adb':'PC_MOCK'}
            with patch.object(mod,'inspect',return_value=([{'session_id':'pending'}],)):
                x=mod.device_check(job,b/'check',client_factory=FakeClient)
            self.assertEqual(set(x['blockers']),{'SOC_BELOW10_OR_UNKNOWN','CHARGING_OR_UNKNOWN','SCREEN_CONTRACT_NOT_READY','PENDING_REMOTE_PATH_EXISTS'})
            self.assertFalse(x['measurement_admitted']);self.assertFalse(x['settings_changed'])
            self.assertEqual([x[k] for k in ['APP','START','claim','inference','instrumentation','measurement','sessions_consumed','APK_install']],[0]*8)


if __name__=='__main__':unittest.main()
