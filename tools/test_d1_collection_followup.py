import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch,Mock
from tools import d1_adb_observed_client as a
from tools import d1_recorded_process as rp
from tools import d1_collection_followup as f
from tools import d1_arrival_collection as c
from tools import d1_arrival_collection_device as runner

class ClientTest(unittest.TestCase):
    def test_server_probe_does_not_launch_adb_and_handles_fragmented_response(self):
        stream=Mock();stream.__enter__=Mock(return_value=stream);stream.__exit__=Mock(return_value=False)
        stream.recv.side_effect=[b'O',b'KAY',b'0004',b'0029']
        with patch.dict(os.environ,{},clear=True),patch.object(a.socket,'create_connection',return_value=stream),patch.object(a.subprocess,'Popen') as popen:
            self.assertEqual(a.server_probe()['protocol_version'],'0029');popen.assert_not_called()

    def test_environment_override_is_not_silently_ignored(self):
        with patch.dict(os.environ,{'ADB_SERVER_SOCKET':'tcp:elsewhere:5037'}),patch.object(a.socket,'create_connection') as connect:
            with self.assertRaises(RuntimeError):a.server_probe()
            connect.assert_not_called()

    def test_wrong_server_version_never_spawns_client(self):
        stream=Mock();stream.__enter__=Mock(return_value=stream);stream.__exit__=Mock(return_value=False)
        stream.recv.side_effect=[b'OKAY',b'0004',b'0028']
        with patch.dict(os.environ,{},clear=True),patch.object(a.socket,'create_connection',return_value=stream):
            with self.assertRaises(RuntimeError):a.server_probe()

    def test_server_absent_no_client_restart_or_retry(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(a,'server_probe',side_effect=ConnectionRefusedError),patch.object(a,'host_snapshot',return_value={}),patch.object(rp,'run') as run:
            d=a.ObservedDevice('never.exe','selected',tmp);d.deadline=time.monotonic()+10
            with self.assertRaises(RuntimeError):d.call('devices','-l')
            run.assert_not_called()
            x=json.loads((Path(tmp)/'0000/context.json').read_text());self.assertFalse(x['client_launch_intent'])

    def test_client_failure_preserves_raw_bytes_and_uses_root_only(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(a,'server_probe',return_value={}),patch.object(a,'host_snapshot',return_value={}):
            def execute(command,output,timeout,display,**kwargs):
                self.assertTrue(kwargs['root_only']);self.assertEqual(command[:3],['exact-adb','-s','selected'])
                output.mkdir();(output/'stdout.bin').write_bytes(b'partial\xff');(output/'stderr.bin').write_bytes(b'5037\xfe')
                return dict(status='nonzero_exit',returncode=1)
            with patch.object(rp,'run',side_effect=execute) as run:
                d=a.ObservedDevice('exact-adb','selected',tmp);d.deadline=time.monotonic()+10
                with self.assertRaises(RuntimeError):d.call('push','input','target')
                self.assertEqual(run.call_count,1)
                self.assertEqual((Path(tmp)/'0000/client/stderr.bin').read_bytes(),b'5037\xfe')

    def test_timeout_kills_only_client_not_tree(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(rp.subprocess,'run',side_effect=AssertionError('taskkill/tree called')):
            x=rp.run([sys.executable,'-c',"import time;print('prefix',flush=True);time.sleep(10)"],Path(tmp)/'run',.5,['python','blocking'],root_only=True)
            self.assertEqual(x['status'],'timeout');self.assertTrue(x['root_reaped'])
            self.assertEqual(x['tree_termination'],'not_attempted_shared_daemon_not_owned')

class FollowupTest(unittest.TestCase):
    def plan(self):
        path=os.environ.get('D1_FOLLOWUP_PLAN')
        if not path:self.skipTest('prepared followup required')
        return Path(path)

    def test_pc_check_no_device_or_server_probe(self):
        with patch.object(a,'server_probe',side_effect=AssertionError('network')),patch.object(a,'ObservedDevice',side_effect=AssertionError('ADB')):
            result=f.check(self.plan())
        self.assertEqual((result['collection']['sessions'],result['explicit_inferences'],result['install_cap'],result['total_seconds']),(3,36,0,1800))

    def test_freeze_reuse_consumption_and_no_development(self):
        path=self.plan();p=c.p.read(path)
        with tempfile.TemporaryDirectory() as tmp:
            p.update(registry=str(Path(tmp)/'registry'),output_root=str(Path(tmp)/'output'))
            test=Path(tmp)/'plan.json';c.cal.write_new(test,p)
            runner.claim(test,'confirmation',p['frozen_development'])
            receipt=c.p.read(Path(p['registry'])/'confirmation_consumed.json')
            self.assertEqual(receipt['freeze_sha256'],p['frozen_development_sha256'])
            self.assertFalse((Path(p['registry'])/'development_complete.json').exists())
            with self.assertRaises(ValueError):runner.claim(test,'confirmation',p['frozen_development'])
            with self.assertRaises(ValueError):runner.run(test,'development','never','never',3,c.p.digest(test))

    def test_mutated_freeze_or_parent_refused(self):
        p=c.p.read(self.plan());p['frozen_development_sha256']='0'*64
        with self.assertRaises(ValueError):f.evidence_gate(p)
        p=c.p.read(self.plan());p['parent_evidence'][next(iter(p['parent_evidence']))]='0'*64
        with self.assertRaises(ValueError):f.evidence_gate(p)

    def test_no_approval_no_plan_access(self):
        with patch.object(f,'check') as check:
            with self.assertRaises(ValueError):f.run('absent','serial',False,'sha')
            check.assert_not_called()

    def test_followup_server_failure_claims_plan_not_session_and_no_install(self):
        p=c.p.read(self.plan())
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'check'),patch.object(f,'evidence_gate'),patch.object(a,'ObservedDevice') as device,patch.object(runner.apk,'preflight',side_effect=RuntimeError('server unavailable')):
            p.update(registry=str(Path(tmp)/'registry'),output_root=str(Path(tmp)/'out'))
            file=Path(tmp)/'plan.json';c.cal.write_new(file,p)
            with self.assertRaises(RuntimeError):runner.run(file,'confirmation','never','selected',3,c.p.digest(file),p['frozen_development'])
            stopped=c.p.read(Path(p['registry'])/'stopped.json')
            self.assertEqual((stopped['attempts'],stopped['launch_attempts'],stopped['install_attempts']),(0,0,0))
            device.return_value.call.assert_not_called()

    def test_followup_different_installed_apk_stops_without_install(self):
        p=c.p.read(self.plan())
        with tempfile.TemporaryDirectory() as tmp,patch.object(c,'check'),patch.object(f,'evidence_gate'),patch.object(a,'ObservedDevice') as device,patch.object(runner.apk,'preflight',return_value=dict(device={},installed='old',candidate='new')),patch.object(runner.legacy,'require_stopped'),patch.object(runner.legacy,'battery_gate'),patch.object(runner.shared,'screen_snapshot'),patch.object(runner.shared,'cleanup',return_value=dict(status='completed')):
            p.update(registry=str(Path(tmp)/'registry'),output_root=str(Path(tmp)/'out'))
            file=Path(tmp)/'plan.json';c.cal.write_new(file,p)
            device.return_value.call.return_value.stdout=b'Thermal Status: 0'
            with self.assertRaises(ValueError):runner.run(file,'confirmation','never','selected',3,c.p.digest(file),p['frozen_development'])
            self.assertFalse(any('install' in call.args for call in device.return_value.call.call_args_list))

    def test_workload_preserved_and_original_denominators_not_rewritten(self):
        p=c.p.read(self.plan());old=c.p.read(p['parent_plan'])
        self.assertEqual([e['condition'] for e in p['entries']],list(f.ORDER))
        self.assertFalse({e['session_id'] for e in p['entries']} & {e['session_id'] for e in old['entries']})
        stop=c.p.read(Path(old['registry'])/'stopped.json')
        self.assertEqual((stop['attempts'],stop['completed']),(4,3))
        self.assertFalse(Path(p['registry']).exists());self.assertFalse(Path(p['output_root']).exists())

if __name__=='__main__':unittest.main()
