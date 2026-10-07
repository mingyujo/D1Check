import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tools import d1_history_recovery_campaign as r


class Clock:
    def __init__(self):self.t=0.
    def now(self):return self.t
    def sleep(self,n):self.t+=n


class RecoveryTests(unittest.TestCase):
    def test_wait_bounded_twenty_minutes_twenty_queries_no_reconnect(self):
        clock=Clock();calls=[];records=[]
        def call(*args,**kwargs):calls.append(args);return SimpleNamespace(returncode=1,stdout=b'',stderr=b'not found')
        d=SimpleNamespace(call=call)
        self.assertFalse(r.wait_online(d,1200,lambda e:records.append(list(e)),clock.sleep,clock.now))
        self.assertEqual(clock.t,1200);self.assertEqual(calls,[('get-state',)]*20)
        self.assertEqual(len(records),20)

    def test_recovery_early_online_and_exception_recorded(self):
        clock=Clock();records=[];count=0
        def call(*args,**kwargs):
            nonlocal count
            count+=1
            if count==1:raise RuntimeError('closed')
            return SimpleNamespace(returncode=0,stdout=b'device\n',stderr=b'')
        self.assertTrue(r.wait_online(SimpleNamespace(call=call),1200,lambda e:records.append(list(e)),clock.sleep,clock.now))
        self.assertEqual(clock.t,60);self.assertEqual(count,2);self.assertIn('error',records[0][0])

    def test_campaign_clock_cannot_reset_and_reserved_time(self):
        claim=dict(monotonic_start=100,wall_start=1000)
        self.assertEqual(r.remaining(claim,200,1100),21500)
        with self.assertRaisesRegex(ValueError,'clock'):r.remaining(claim,50,1100)
        with self.assertRaisesRegex(ValueError,'clock'):r.remaining(claim,200,1200)
        self.assertEqual(r.limits()['explicit_inference'],r.h.budget()['explicit_inference']+104)
        self.assertEqual(r.limits()['adb_commands'],r.h.budget()['adb_commands']+7800+40)
        self.assertLess(r.h.budget()['total_seconds']+1200+120+600,21600)

    def test_repair_eligibility_stops_late_or_non_app_failures(self):
        with tempfile.TemporaryDirectory() as t:
            receipt=dict(status='stopped_no_resume',completed_sessions=0,session_attempts=1,launch_attempts=1)
            with self.assertRaisesRegex(ValueError,'no durable app'):r.repair_eligibility(receipt,t)
            folder=Path(t)/'00_fixture/artifacts';folder.mkdir(parents=True)
            (folder/'session_failure.json').write_text('{}')
            self.assertEqual(len(r.repair_eligibility(receipt,t)),1)
            for change in ({'completed_sessions':1},{'session_attempts':2},{'launch_attempts':0},{'status':'completed_descriptive_only'}):
                with self.assertRaisesRegex(ValueError,'before any eligible'):r.repair_eligibility(dict(receipt,**change),t)

    def test_standalone_child_cannot_bypass_campaign(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,'campaign owner'):r.require_admission('unused')

    def test_readonly_wrong_device_never_pulls_or_stops_app(self):
        calls=[]
        def call(*args,**kw):calls.append(args);return SimpleNamespace(stdout=b'wrong',returncode=0,stderr=b'')
        child=dict(device_fingerprint='expected',device_hardware_serial='expected')
        with self.assertRaisesRegex(ValueError,'device differs'):r.recover_readonly(SimpleNamespace(call=call),child,'unused')
        self.assertEqual(len(calls),3);self.assertTrue(all(x[:2]==('shell','getprop') for x in calls))

    def test_active_child_or_unreaped_client_blocks_recovery(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);reg=root/'registry';reg.mkdir();r.write(reg/'claimed.json',dict(host_identity={'child':{}}))
            child=dict(registry=str(reg),output_root=str(root/'run'))
            with patch.object(r.life,'identity_state',return_value='active'):
                with self.assertRaisesRegex(ValueError,'alive/unknown'):r.child_exited(child)
            log=root/'run/host_commands/0000/client';log.mkdir(parents=True)
            r.write(log/'result.json',dict(status='timeout',returncode=None))
            with patch.object(r.life,'identity_state',return_value='exited'):
                with self.assertRaisesRegex(ValueError,'client state'):r.child_exited(child)

    def test_no_repair_start_without_full_time_reservation(self):
        with tempfile.TemporaryDirectory() as t,patch.object(r,'remaining',return_value=1000),patch.object(r.subprocess,'run',side_effect=AssertionError('must not launch')) as run:
            file=Path(t)/'child.json';r.write(file,dict(budget=r.h.budget()))
            with self.assertRaisesRegex(ValueError,'full block'):r.invoke(file,t,'FAKE','FAKE',{},'repair')
            run.assert_not_called();self.assertEqual(list(Path(t).iterdir()),[file])

    def test_readonly_terminal_session_recovery_never_launches_or_force_stops(self):
        from tools import d1_energy_collection_device as energy
        import hashlib
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);session=root/'run/00_fixture';session.mkdir(parents=True)
            (session/'launch_attempt.json').write_text('{}')
            raw=b'{"session_id":"fixture"}';(session/'input_manifest.json').write_bytes(raw)
            child=dict(output_root=str(root/'run'),device_fingerprint='fingerprint',device_hardware_serial='hardware',protocol='fixture-protocol')
            calls=[]
            def call(*args,**kwargs):
                calls.append(args)
                value={('shell','getprop','ro.product.model'):b'SM-A245N',('shell','getprop','ro.build.fingerprint'):b'fingerprint',('shell','getprop','ro.serialno'):b'hardware'}.get(args)
                if args[0]=='exec-out':value=raw if args[-1].endswith('manifest.json') else b'{"status":"completed"}'
                if args[:2]==('shell','pidof'):return SimpleNamespace(returncode=1,stdout=b'',stderr=b'')
                return SimpleNamespace(returncode=0,stdout=value,stderr=b'')
            with patch.object(energy,'recover',return_value={'status':'recovered'}) as recover:
                result=r.recover_readonly(SimpleNamespace(call=call),child,root/'recovery')
                self.assertEqual(result['process'],'absent');recover.assert_called_once()
            self.assertEqual(len(calls),6)
            self.assertFalse(any(any(x in args for x in ('force-stop','start','connect','push','install')) for args in calls))

    def test_admission_checks_parent_hash_token_and_remaining_time(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);file=root/'child.json';permit=root/'permit.json'
            r.write(file,dict(history_recovery_child={'campaign_root':str(root)},budget=r.h.budget()))
            r.write(root/'claim.json',dict(token='fixture'))
            r.write(permit,dict(parent_pid=os.getppid(),plan_sha256=r.sha(file),campaign_token='fixture'))
            with patch.dict(os.environ,{r.ENV:str(permit)}),patch.object(r,'remaining',return_value=21600):r.require_admission(file)
            with patch.dict(os.environ,{r.ENV:str(permit)}),patch.object(r,'remaining',return_value=100):
                with self.assertRaisesRegex(ValueError,'time admission'):r.require_admission(file)


if __name__=='__main__':unittest.main()
